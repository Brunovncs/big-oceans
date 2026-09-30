package dev.bigoceans.lab;

import com.google.gson.Gson;
import com.google.gson.GsonBuilder;
import com.google.gson.JsonArray;
import com.google.gson.JsonObject;
import net.fabricmc.api.DedicatedServerModInitializer;
import net.fabricmc.fabric.api.event.lifecycle.v1.ServerLifecycleEvents;
import net.minecraft.core.BlockPos;
import net.minecraft.core.Holder;
import net.minecraft.core.HolderGetter;
import net.minecraft.core.QuartPos;
import net.minecraft.core.registries.Registries;
import net.minecraft.resources.ResourceKey;
import net.minecraft.resources.ResourceLocation;
import net.minecraft.server.MinecraftServer;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.world.level.biome.Biome;
import net.minecraft.world.level.biome.BiomeSource;
import net.minecraft.world.level.levelgen.DensityFunction;
import net.minecraft.world.level.levelgen.DensityFunctions;
import net.minecraft.world.level.levelgen.Heightmap;
import net.minecraft.world.level.levelgen.NoiseBasedChunkGenerator;
import net.minecraft.world.level.levelgen.NoiseGeneratorSettings;
import net.minecraft.world.level.levelgen.Noises;
import net.minecraft.world.level.levelgen.RandomState;
import net.minecraft.world.level.levelgen.synth.NormalNoise;
import dev.bigoceans.worldgen.OceanBasinsFunction;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.io.DataOutputStream;
import java.io.BufferedOutputStream;
import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.List;
import java.util.Map;
import java.util.Optional;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.ForkJoinPool;
import java.util.concurrent.atomic.AtomicInteger;
import java.util.function.UnaryOperator;
import java.util.stream.IntStream;

/**
 * Dev-only analysis harness. Started inside a dedicated dev server, it samples the real noise terrain
 * ({@code getBaseHeight}, i.e. pre-feature terrain) and surface biomes over large grids for arbitrary seeds and
 * continentalness variants, writes raw grids for the Python analysis, then stops the server.
 */
public class WorldgenLab implements DedicatedServerModInitializer {
    private static final Logger LOG = LoggerFactory.getLogger("BigOceansLab");
    private static final Gson GSON = new GsonBuilder().setPrettyPrinting().create();

    record ShapeParams(double k, double t, double w, double land, double ceil) {}

    @Override
    public void onInitializeServer() {
        String jobs = System.getProperty("bigoceans.lab.jobs");
        if (jobs == null) return;
        ServerLifecycleEvents.SERVER_STARTED.register(server -> {
            try {
                run(server, Path.of(jobs));
            } catch (Exception e) {
                LOG.error("Lab failed", e);
            }
            server.halt(false);
        });
    }

    private void run(MinecraftServer server, Path jobsFile) throws IOException {
        JsonObject root = GSON.fromJson(Files.readString(jobsFile), JsonObject.class);
        Path out = jobsFile.toAbsolutePath().getParent().resolve(root.get("out").getAsString()).normalize();
        Files.createDirectories(out);
        int threads = root.has("threads") ? root.get("threads").getAsInt() : Runtime.getRuntime().availableProcessors() - 1;
        ForkJoinPool pool = new ForkJoinPool(threads);
        for (var el : root.getAsJsonArray("jobs")) {
            JsonObject job = el.getAsJsonObject();
            String name = job.get("name").getAsString();
            if (Files.exists(out.resolve(name + ".json")) && !root.has("overwrite")) {
                LOG.info("skip {}", name);
                continue;
            }
            long t0 = System.nanoTime();
            JsonObject meta = sample(server, job, out.resolve(name + ".bin"), pool);
            meta.addProperty("seconds", (System.nanoTime() - t0) / 1e9);
            Files.writeString(out.resolve(name + ".json"), GSON.toJson(meta));
            LOG.info("done {} in {}s", name, meta.get("seconds").getAsDouble());
        }
        pool.shutdown();
    }

    private JsonObject sample(MinecraftServer server, JsonObject job, Path bin, ForkJoinPool pool) throws IOException {
        long seed = job.get("seed").getAsLong();
        int radius = job.get("radius").getAsInt();
        int step = job.get("step").getAsInt();
        int cx = job.has("cx") ? job.get("cx").getAsInt() : 0;
        int cz = job.has("cz") ? job.get("cz").getAsInt() : 0;
        JsonObject variant = job.getAsJsonObject("variant");

        ServerLevel level = server.overworld();
        var access = server.registryAccess();
        HolderGetter<NormalNoise.NoiseParameters> noises = access.lookupOrThrow(Registries.NOISE);
        var dfs = access.lookupOrThrow(Registries.DENSITY_FUNCTION);
        Holder<NoiseGeneratorSettings> settingsHolder = access.lookupOrThrow(Registries.NOISE_SETTINGS).getOrThrow(NoiseGeneratorSettings.OVERWORLD);
        NoiseGeneratorSettings base = settingsHolder.value();
        // Every variant replaces the mod's OceanBasinsFunction node (installed by the continents override).
        String family = variant.get("family").getAsString();
        UnaryOperator<DensityFunction> replace = switch (family) {
            case "registry" -> UnaryOperator.identity();
            case "vanilla" -> f -> f instanceof OceanBasinsFunction o ? o.argument() : f;
            case "scale" -> {
                Optional<Double> scale = Optional.of(variant.get("scale").getAsDouble());
                yield f -> f instanceof OceanBasinsFunction o ? new OceanBasinsFunction(o.argument(), o.noise(), o.xzScale(), scale, null) : f;
            }
            case "shape" -> {
                var sh = GSON.fromJson(variant, ShapeParams.class);
                var shape = OceanBasinsFunction.BasinShape.of(sh.k, sh.t, sh.w, sh.land, sh.ceil);
                yield f -> f instanceof OceanBasinsFunction o ? new OceanBasinsFunction(o.argument(), o.noise(), o.xzScale(), Optional.empty(), shape) : f;
            }
            default -> {
                var v = GSON.fromJson(variant, ExperimentalContinents.Variant.class);
                var contNoise = new DensityFunction.NoiseHolder(noises.getOrThrow(Noises.CONTINENTALNESS));
                var shiftX = new DensityFunctions.HolderHolder(dfs.getOrThrow(ResourceKey.create(Registries.DENSITY_FUNCTION, ResourceLocation.withDefaultNamespace("shift_x"))));
                var shiftZ = new DensityFunctions.HolderHolder(dfs.getOrThrow(ResourceKey.create(Registries.DENSITY_FUNCTION, ResourceLocation.withDefaultNamespace("shift_z"))));
                yield f -> f instanceof OceanBasinsFunction o ? new ExperimentalContinents(o.argument(), contNoise, shiftX, shiftZ, v) : f;
            }
        };
        var router = base.noiseRouter().mapAll(replace::apply);
        NoiseGeneratorSettings settings = new NoiseGeneratorSettings(base.noiseSettings(), base.defaultBlock(), base.defaultFluid(),
                router, base.surfaceRule(), base.spawnTarget(), base.seaLevel(), base.disableMobGeneration(),
                base.aquifersEnabled(), base.oreVeinsEnabled(), base.useLegacyRandomSource());

        BiomeSource biomes = ((NoiseBasedChunkGenerator) level.getChunkSource().getGenerator()).getBiomeSource();
        NoiseBasedChunkGenerator gen = new NoiseBasedChunkGenerator(biomes, Holder.direct(settings));
        RandomState rs = RandomState.create(settings, noises, seed);
        int sea = settings.seaLevel();

        int n = 2 * radius / step;
        short[] height = new short[n * n];
        short[] biome = new short[n * n];
        float[] cont = new float[n * n];
        Map<Holder<Biome>, Short> palette = new ConcurrentHashMap<>();
        AtomicInteger next = new AtomicInteger();
        pool.submit(() -> IntStream.range(0, n).parallel().forEach(j -> {
            int z = cz - radius + j * step + step / 2;
            for (int i = 0; i < n; i++) {
                int x = cx - radius + i * step + step / 2;
                int h = gen.getBaseHeight(x, z, Heightmap.Types.OCEAN_FLOOR_WG, level, rs);
                Holder<Biome> b = biomes.getNoiseBiome(QuartPos.fromBlock(x), QuartPos.fromBlock(Math.max(h, sea)), QuartPos.fromBlock(z), rs.sampler());
                int idx = j * n + i;
                height[idx] = (short) h;
                biome[idx] = palette.computeIfAbsent(b, k -> (short) next.getAndIncrement());
                cont[idx] = (float) rs.router().continents().compute(new DensityFunction.SinglePointContext(x, 0, z));
            }
        })).join();

        try (var os = new DataOutputStream(new BufferedOutputStream(Files.newOutputStream(bin), 1 << 20))) {
            for (short h : height) os.writeShort(h);
            for (short b : biome) os.writeShort(b);
            for (float c : cont) os.writeFloat(c);
        }

        BlockPos spawn = rs.sampler().findSpawnPosition();
        JsonObject meta = new JsonObject();
        meta.add("job", job);
        meta.addProperty("n", n);
        meta.addProperty("sea_level", sea);
        String[] names = new String[palette.size()];
        palette.forEach((h, i) -> names[i] = h.unwrapKey().orElseThrow().location().toString());
        JsonArray pal = new JsonArray();
        for (String s : names) pal.add(s);
        meta.add("palette", pal);
        JsonObject sp = new JsonObject();
        sp.addProperty("x", spawn.getX());
        sp.addProperty("z", spawn.getZ());
        sp.addProperty("height", gen.getBaseHeight(spawn.getX(), spawn.getZ(), Heightmap.Types.OCEAN_FLOOR_WG, level, rs));
        sp.addProperty("biome", biomes.getNoiseBiome(QuartPos.fromBlock(spawn.getX()), QuartPos.fromBlock(sea), QuartPos.fromBlock(spawn.getZ()), rs.sampler())
                .unwrapKey().orElseThrow().location().toString());
        meta.add("spawn", sp);
        return meta;
    }
}
