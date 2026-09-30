package dev.bigoceans.neoforge;

import com.mojang.serialization.MapCodec;
import dev.bigoceans.BigOceans;
import dev.bigoceans.worldgen.OceanBasinsFunction;
import net.minecraft.core.registries.Registries;
import net.minecraft.world.level.levelgen.DensityFunction;
import net.minecraft.world.level.storage.LevelResource;
import net.neoforged.bus.api.IEventBus;
import net.neoforged.fml.common.Mod;
import net.neoforged.fml.loading.FMLPaths;
import net.neoforged.neoforge.common.NeoForge;
import net.neoforged.neoforge.event.server.ServerAboutToStartEvent;
import net.neoforged.neoforge.registries.DeferredRegister;

@Mod(BigOceans.MOD_ID)
public class BigOceansNeoForge {
    private static final DeferredRegister<MapCodec<? extends DensityFunction>> DENSITY_FUNCTION_TYPES =
            DeferredRegister.create(Registries.DENSITY_FUNCTION_TYPE, BigOceans.MOD_ID);

    static {
        DENSITY_FUNCTION_TYPES.register(BigOceans.OCEAN_BASINS, OceanBasinsFunction.CODEC::codec);
    }

    public BigOceansNeoForge(IEventBus modBus) {
        DENSITY_FUNCTION_TYPES.register(modBus);
        NeoForge.EVENT_BUS.addListener((ServerAboutToStartEvent event) ->
                BigOceans.onServerStarting(event.getServer().getWorldPath(LevelResource.ROOT), FMLPaths.CONFIGDIR.get()));
    }
}
