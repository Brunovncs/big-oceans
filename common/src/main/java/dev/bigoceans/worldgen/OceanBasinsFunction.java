package dev.bigoceans.worldgen;

import com.mojang.serialization.Codec;
import com.mojang.serialization.MapCodec;
import com.mojang.serialization.codecs.RecordCodecBuilder;
import dev.bigoceans.BigOceans;
import dev.bigoceans.BigOceansConfig;
import net.minecraft.util.KeyDispatchDataCodec;
import net.minecraft.util.Mth;
import net.minecraft.world.level.levelgen.DensityFunction;

import java.util.Optional;

/**
 * Wraps vanilla continentalness and carves ocean basins into it at a larger geographic scale.
 *
 * <p>A second, much lower-frequency noise ({@code noise}) decides where the basins are. Deep inside a basin, the
 * vanilla continentalness is compressed into the deep-ocean band, so terrain there becomes deep ocean floor (vanilla
 * mushroom-island cores, which sit below that band, are kept). Away from basins a small positive bias merges vanilla
 * land into continents. Near basin edges the result is still dominated by the vanilla value, so coastlines, beaches
 * and biome transitions keep their vanilla shape and width.
 *
 * <p>Parameters are resolved when the function is wired into a {@code RandomState}, i.e. per world, from
 * {@link BigOceans#settings()}, unless a datapack pins {@code ocean_scale} explicitly.
 */
public record OceanBasinsFunction(DensityFunction argument, DensityFunction.NoiseHolder noise, double xzScale,
                                  Optional<Double> oceanScale, BasinShape shape) implements DensityFunction {

    public static final MapCodec<OceanBasinsFunction> DATA_CODEC = RecordCodecBuilder.mapCodec(i -> i.group(
            DensityFunction.HOLDER_HELPER_CODEC.fieldOf("argument").forGetter(OceanBasinsFunction::argument),
            DensityFunction.NoiseHolder.CODEC.fieldOf("noise").forGetter(OceanBasinsFunction::noise),
            Codec.doubleRange(1e-6, 16).fieldOf("xz_scale").forGetter(OceanBasinsFunction::xzScale),
            Codec.doubleRange(BasinShape.MIN_SCALE, BasinShape.MAX_SCALE).optionalFieldOf("ocean_scale").forGetter(OceanBasinsFunction::oceanScale)
    ).apply(i, (argument, noise, xzScale, scale) -> new OceanBasinsFunction(argument, noise, xzScale, scale, null)));
    public static final KeyDispatchDataCodec<OceanBasinsFunction> CODEC = KeyDispatchDataCodec.of(DATA_CODEC);

    /** Vanilla continentalness below this is a mushroom-island core; it is passed through untouched. */
    private static final double MUSHROOM_CORE = -1.02;
    static final double SPAWN_INNER = 1024.0;
    static final double SPAWN_OUTER = 2560.0;

    @Override
    public double compute(FunctionContext ctx) {
        double c = argument.compute(ctx);
        BasinShape s = resolvedShape();
        if (s.isVanilla()) return c;
        double scale = xzScale / s.wavelength();
        double field = noise.getValue(ctx.blockX() * scale + BasinShape.OFFSET, 0, ctx.blockZ() * scale + BasinShape.OFFSET);
        double shaped = s.apply(c, field);
        double fade = spawnFade(ctx.blockX(), ctx.blockZ());
        return fade >= 1.0 ? shaped : c + fade * (shaped - c);
    }

    /**
     * 0 near the world origin, 1 beyond {@link #SPAWN_OUTER}. Vanilla's spawn search only looks within 2048 blocks of
     * the origin for land-like climate, so the basins fade out there and the spawn area keeps vanilla geography.
     */
    static double spawnFade(int x, int z) {
        double d2 = (double) x * x + (double) z * z;
        if (d2 >= SPAWN_OUTER * SPAWN_OUTER) return 1.0;
        double t = Mth.clamp((Math.sqrt(d2) - SPAWN_INNER) / (SPAWN_OUTER - SPAWN_INNER), 0.0, 1.0);
        return t * t * (3.0 - 2.0 * t);
    }

    private BasinShape resolvedShape() {
        return shape != null ? shape : BasinShape.forScale(oceanScale.orElseGet(() -> BigOceans.settings().oceanScale()));
    }

    @Override
    public void fillArray(double[] out, ContextProvider provider) {
        provider.fillAllDirectly(out, this);
    }

    @Override
    public DensityFunction mapAll(Visitor visitor) {
        return visitor.apply(new OceanBasinsFunction(argument.mapAll(visitor), visitor.visitNoise(noise), xzScale, oceanScale, resolvedShape()));
    }

    @Override
    public double minValue() {
        return Math.min(argument.minValue(), MUSHROOM_CORE);
    }

    @Override
    public double maxValue() {
        return argument.maxValue() + BasinShape.MAX_LAND_BIAS;
    }

    @Override
    public KeyDispatchDataCodec<? extends DensityFunction> codec() {
        return CODEC;
    }

    /**
     * The basin geometry for one ocean scale.
     *
     * @param wavelength how many times larger than vanilla continentalness the basin field is
     * @param threshold  basin field value at which a basin starts
     * @param width      field distance over which a basin fades in to full depth (and land bias fades in)
     * @param landBias   continentalness added far from basins, merging vanilla land into continents
     * @param ceiling    highest continentalness a basin core can keep; above -0.11 rare mid-ocean islands appear
     * @param strength   0..1 blend towards vanilla, so scales just above 1.0 are close to vanilla
     */
    public record BasinShape(double wavelength, double threshold, double width, double landBias, double ceiling, double strength) {
        public static final double MIN_SCALE = 1.0;
        public static final double MAX_SCALE = BigOceansConfig.MAX_OCEAN_SCALE;
        static final double MAX_LAND_BIAS = 0.5;
        private static final double VANILLA_MAX = 1.2;
        private static final BasinShape VANILLA = new BasinShape(1, 0, 0, 0, 0, 0);
        /** Noise-space offset so the basin field is not correlated with vanilla continentalness around the origin. */
        static final double OFFSET = 10_000.0;

        public boolean isVanilla() {
            return strength <= 0;
        }

        double apply(double c, double field) {
            double ocean = smoothstep((threshold - field) / width);
            double land = smoothstep((field - threshold) / width);
            double deep = c < MUSHROOM_CORE ? c : MUSHROOM_CORE + (c - MUSHROOM_CORE) * (ceiling - MUSHROOM_CORE) / (VANILLA_MAX - MUSHROOM_CORE);
            return c + strength * (ocean * (deep - c) + land * landBias);
        }

        private static double smoothstep(double x) {
            x = Mth.clamp(x, 0.0, 1.0);
            return x * x * (3.0 - 2.0 * x);
        }

        public static BasinShape of(double wavelength, double threshold, double width, double landBias, double ceiling) {
            return new BasinShape(wavelength, threshold, width, Mth.clamp(landBias, 0, MAX_LAND_BIAS), ceiling, 1.0);
        }

        /**
         * Maps the user-facing ocean scale onto basin geometry; 1.0 is exactly vanilla. Calibrated with the lab (see
         * the README): basin coverage ramps up until 4.0, where the world ocean becomes connected, and from
         * there only the basin size keeps growing. Below 4.0 the basins keep the 4.0 size and are just rarer, which
         * gives larger open oceans than many small basins, and ramping coverage faster fragments the land.
         */
        public static BasinShape forScale(double scale) {
            scale = Mth.clamp(scale, MIN_SCALE, MAX_SCALE);
            if (scale <= MIN_SCALE) return VANILLA;
            double ramp = Math.min(1.0, (scale - 1.0) / 3.0);
            double strength = smoothstep((scale - 1.0) / 0.5);
            return new BasinShape(Math.pow(Math.max(scale, 4.0), 1.1), -0.5 + 0.6 * ramp, 0.3, 0.2 * ramp, -0.15, strength);
        }
    }
}
