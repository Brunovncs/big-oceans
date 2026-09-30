package dev.bigoceans;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.stream.Stream;

public final class BigOceans {
    public static final String MOD_ID = "big_oceans";
    public static final Logger LOGGER = LoggerFactory.getLogger("Big Oceans");
    /** Path of the density function type; the registry id is {@code big_oceans:ocean_basins}. */
    public static final String OCEAN_BASINS = "ocean_basins";
    public static final String CONFIG_FILE = "big_oceans.toml";

    private static final String GLOBAL_HEADER = """
            # Big Oceans - default settings for NEW worlds.
            # Each world copies these into <world>/big_oceans.toml the first time it is loaded and keeps using its own copy.
            #
            # ocean_scale: how much larger oceans are than vanilla.
            #   1.0 = vanilla, 2.0 = somewhat larger seas, 3.0 = large seas, 4.0 = one connected world ocean with
            #   ~5x wider crossings (default). Above 4.0 the ocean share stays about the same (~58%) and only the
            #   oceans and continents get wider. Valid range 1.0 - 8.0; fractional values are fine.
            """;
    private static final String WORLD_HEADER = """
            # Big Oceans settings for THIS world.
            # Changing them later only affects chunks generated afterwards and leaves visible seams at the boundary.
            """;

    private static volatile BigOceansConfig settings = BigOceansConfig.DEFAULT;

    private BigOceans() {
    }

    /** Settings used by density functions wired from now on. */
    public static BigOceansConfig settings() {
        return settings;
    }

    /**
     * Resolves the settings for the world about to load. Must run before the server creates its levels, which is
     * when the overworld's {@code RandomState} (and with it every {@link dev.bigoceans.worldgen.OceanBasinsFunction})
     * is built.
     */
    public static void onServerStarting(Path worldDir, Path configDir) {
        BigOceansConfig global = BigOceansConfig.loadOrCreate(configDir.resolve(CONFIG_FILE), BigOceansConfig.DEFAULT, GLOBAL_HEADER);
        Path worldFile = worldDir.resolve(CONFIG_FILE);
        boolean firstRun = !Files.exists(worldFile);
        if (firstRun && hasGeneratedChunks(worldDir)) {
            LOGGER.warn("Big Oceans was added to an existing world. Chunks that already exist keep their terrain; newly "
                    + "generated chunks use ocean_scale={}, so expect visible seams where they meet.", global.oceanScale());
        }
        settings = BigOceansConfig.loadOrCreate(worldFile, global, WORLD_HEADER);
        LOGGER.info("Big Oceans active with ocean_scale={} ({})", settings.oceanScale(), firstRun ? "new world settings" : worldFile);
    }

    private static boolean hasGeneratedChunks(Path worldDir) {
        Path region = worldDir.resolve("region");
        if (!Files.isDirectory(region)) return false;
        try (Stream<Path> files = Files.list(region)) {
            return files.findAny().isPresent();
        } catch (IOException e) {
            return false;
        }
    }
}
