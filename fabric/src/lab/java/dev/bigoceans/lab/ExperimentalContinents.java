package dev.bigoceans.lab;

import com.mojang.serialization.MapCodec;
import net.minecraft.util.KeyDispatchDataCodec;
import net.minecraft.world.level.levelgen.DensityFunction;

/**
 * Lab-only continentalness replacements that were evaluated and rejected (see the README): {@code stretch}
 * scales vanilla continentalness up as a whole, {@code blend} mixes it with a large-scale copy.
 * {@code vanilla} is the untouched vanilla continents function; {@code noise} is the vanilla continentalness noise,
 * resampled here at a larger geographic scale.
 */
public record ExperimentalContinents(DensityFunction vanilla, DensityFunction.NoiseHolder noise,
                                     DensityFunction shiftX, DensityFunction shiftZ, Variant v) implements DensityFunction {

    /** Noise-space offset that decorrelates the large-scale field from the vanilla field sampled near the same origin. */
    static final double DECORRELATE = 10_000.0;

    public record Variant(String family, double k, double a, double b, double floor) {}

    @Override
    public double compute(FunctionContext ctx) {
        double c = vanilla.compute(ctx);
        double s = 0.25 / v.k();
        return switch (v.family()) {
            case "stretch" -> noise.getValue(ctx.blockX() * s + shiftX.compute(ctx) / v.k(), 0, ctx.blockZ() * s + shiftZ.compute(ctx) / v.k());
            case "blend" -> {
                double big = large(ctx, s);
                yield softFloor(v.a() * big + (1 - v.a()) * c + v.b(), v.floor());
            }
            default -> c;
        };
    }

    private double large(FunctionContext ctx, double s) {
        return noise.getValue(ctx.blockX() * s + DECORRELATE, 0, ctx.blockZ() * s + DECORRELATE);
    }

    /** Keeps very low values inside the deep-ocean band instead of letting them reach mushroom-island continentalness. */
    private static double softFloor(double u, double floor) {
        double knee = -0.6;
        if (floor >= knee || u >= knee) return u;
        double span = knee - floor;
        return knee - span * Math.tanh((knee - u) / span);
    }

    @Override
    public void fillArray(double[] out, ContextProvider provider) {
        provider.fillAllDirectly(out, this);
    }

    @Override
    public DensityFunction mapAll(Visitor visitor) {
        return visitor.apply(new ExperimentalContinents(vanilla.mapAll(visitor), visitor.visitNoise(noise),
                shiftX.mapAll(visitor), shiftZ.mapAll(visitor), v));
    }

    @Override
    public double minValue() {
        return -2;
    }

    @Override
    public double maxValue() {
        return 2;
    }

    @Override
    public KeyDispatchDataCodec<? extends DensityFunction> codec() {
        return KeyDispatchDataCodec.of(MapCodec.unit(this));
    }
}
