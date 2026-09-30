package dev.bigoceans;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.Locale;

/**
 * The user-facing settings, stored as a tiny TOML file. Only flat {@code key = value} lines are understood, which is
 * all this file needs, so no TOML library is bundled.
 */
public record BigOceansConfig(double oceanScale) {
    public static final double DEFAULT_OCEAN_SCALE = 4.0;
    public static final double MAX_OCEAN_SCALE = 8.0;
    public static final BigOceansConfig DEFAULT = new BigOceansConfig(DEFAULT_OCEAN_SCALE);
    public static final BigOceansConfig VANILLA = new BigOceansConfig(1.0);

    public static BigOceansConfig parse(String text) {
        double scale = DEFAULT_OCEAN_SCALE;
        for (String raw : text.split("\\R")) {
            int hash = raw.indexOf('#');
            String line = (hash >= 0 ? raw.substring(0, hash) : raw).trim();
            int eq = line.indexOf('=');
            if (eq < 0) continue;
            String key = line.substring(0, eq).trim();
            String value = line.substring(eq + 1).trim();
            if (key.equals("ocean_scale")) {
                try {
                    scale = Double.parseDouble(value);
                } catch (NumberFormatException e) {
                    BigOceans.LOGGER.warn("Ignoring invalid ocean_scale '{}', using {}", value, DEFAULT_OCEAN_SCALE);
                }
            }
        }
        return new BigOceansConfig(scale).sanitized();
    }

    public BigOceansConfig sanitized() {
        if (Double.isNaN(oceanScale)) return DEFAULT;
        double clamped = Math.max(1.0, Math.min(MAX_OCEAN_SCALE, oceanScale));
        if (clamped != oceanScale) BigOceans.LOGGER.warn("ocean_scale {} is outside 1.0-{}, using {}", oceanScale, MAX_OCEAN_SCALE, clamped);
        return new BigOceansConfig(clamped);
    }

    public String toToml(String header) {
        return header + String.format(Locale.ROOT, "ocean_scale = %s%n", oceanScale);
    }

    /** Reads {@code file}, creating it with {@code fallback} and {@code header} when it does not exist. */
    public static BigOceansConfig loadOrCreate(Path file, BigOceansConfig fallback, String header) {
        try {
            if (Files.exists(file)) return parse(Files.readString(file));
            Files.createDirectories(file.getParent());
            Files.writeString(file, fallback.toToml(header));
        } catch (IOException e) {
            BigOceans.LOGGER.error("Could not read or write {}, using ocean_scale {}", file, fallback.oceanScale(), e);
        }
        return fallback;
    }
}
