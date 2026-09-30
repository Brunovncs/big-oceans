package dev.bigoceans.worldgen;

import dev.bigoceans.worldgen.OceanBasinsFunction.BasinShape;
import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;

class BasinShapeTest {
    private static final double[] SCALES = {1.5, 2, 3, 4, 5, 6, 8};

    @Test
    void scaleOneIsExactlyVanilla() {
        assertTrue(BasinShape.forScale(1.0).isVanilla());
        assertTrue(BasinShape.forScale(0.5).isVanilla());
    }

    @Test
    void farFromBasinsOnlyTheLandBiasIsAdded() {
        for (double scale : SCALES) {
            BasinShape s = BasinShape.forScale(scale);
            for (double c = -1.2; c <= 1.2; c += 0.05) {
                assertEquals(c + s.strength() * s.landBias(), s.apply(c, s.threshold() + 2 * s.width()), 1e-12);
            }
        }
    }

    @Test
    void basinCoresStayInDeepOceanBandButKeepMushroomCores() {
        for (double scale : SCALES) {
            BasinShape s = BasinShape.forScale(scale);
            double core = s.threshold() - 2 * s.width();
            for (double c = -1.0; c <= 1.2; c += 0.05) {
                double out = s.apply(c, core);
                assertTrue(out >= -1.021 && out <= s.ceiling() + 1e-9, "scale " + scale + " c " + c + " -> " + out);
            }
            assertEquals(-1.1, s.apply(-1.1, core), 1e-12);
        }
    }

    @Test
    void closeToVanillaJustAboveOne() {
        BasinShape s = BasinShape.forScale(1.01);
        for (double f = -1.5; f <= 1.5; f += 0.05) {
            for (double c = -1.0; c <= 1.2; c += 0.05) {
                assertEquals(c, s.apply(c, f), 0.01);
            }
        }
    }

    @Test
    void continuousAndMonotonicInBothInputs() {
        for (double scale : SCALES) {
            BasinShape s = BasinShape.forScale(scale);
            for (double f = -1.5; f <= 1.5; f += 0.01) {
                double prev = Double.NEGATIVE_INFINITY;
                for (double c = -1.3; c <= 1.3; c += 0.01) {
                    double v = s.apply(c, f);
                    assertTrue(v >= prev - 1e-12, "not monotonic in continentalness");
                    assertTrue(Math.abs(s.apply(c + 1e-6, f) - v) < 1e-3, "discontinuous in continentalness");
                    assertTrue(Math.abs(s.apply(c, f + 1e-6) - v) < 1e-3, "discontinuous in basin field");
                    assertTrue(s.apply(c, f + 0.01) >= v - 1e-12, "not monotonic in basin field");
                    prev = v;
                }
            }
        }
    }
}
