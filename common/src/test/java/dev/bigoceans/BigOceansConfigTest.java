package dev.bigoceans;

import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;

import java.nio.file.Files;
import java.nio.file.Path;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;

class BigOceansConfigTest {
    @Test
    void parsesScaleWithCommentsAndWhitespace() {
        assertEquals(2.5, BigOceansConfig.parse("# header\n  ocean_scale =  2.5   # inline\n").oceanScale());
    }

    @Test
    void missingOrInvalidValueFallsBackToDefault() {
        assertEquals(BigOceansConfig.DEFAULT_OCEAN_SCALE, BigOceansConfig.parse("").oceanScale());
        assertEquals(BigOceansConfig.DEFAULT_OCEAN_SCALE, BigOceansConfig.parse("ocean_scale = lots").oceanScale());
        assertEquals(BigOceansConfig.DEFAULT_OCEAN_SCALE, BigOceansConfig.parse("ocean_scale = NaN").oceanScale());
    }

    @Test
    void clampsOutOfRangeValues() {
        assertEquals(1.0, BigOceansConfig.parse("ocean_scale = 0.2").oceanScale());
        assertEquals(BigOceansConfig.MAX_OCEAN_SCALE, BigOceansConfig.parse("ocean_scale = 99").oceanScale());
    }

    @Test
    void roundTripsThroughFile(@TempDir Path dir) throws Exception {
        Path file = dir.resolve("sub").resolve("big_oceans.toml");
        BigOceansConfig written = BigOceansConfig.loadOrCreate(file, new BigOceansConfig(3.0), "# test\n");
        assertEquals(3.0, written.oceanScale());
        assertTrue(Files.readString(file).contains("ocean_scale = 3.0"));
        assertEquals(3.0, BigOceansConfig.loadOrCreate(file, BigOceansConfig.DEFAULT, "").oceanScale());
    }

    @Test
    void worldFileTakesPrecedenceOverGlobalConfig(@TempDir Path dir) throws Exception {
        Path config = dir.resolve("config");
        Path world = dir.resolve("world");
        Files.createDirectories(config);
        Files.writeString(config.resolve(BigOceans.CONFIG_FILE), "ocean_scale = 2.0\n");

        BigOceans.onServerStarting(world, config);
        assertEquals(2.0, BigOceans.settings().oceanScale(), "new world copies the global default");

        Files.writeString(config.resolve(BigOceans.CONFIG_FILE), "ocean_scale = 6.0\n");
        BigOceans.onServerStarting(world, config);
        assertEquals(2.0, BigOceans.settings().oceanScale(), "existing world keeps its own settings");
    }
}
