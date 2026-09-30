package dev.bigoceans.fabric;

import dev.bigoceans.BigOceans;
import dev.bigoceans.worldgen.OceanBasinsFunction;
import net.fabricmc.api.ModInitializer;
import net.fabricmc.fabric.api.event.lifecycle.v1.ServerLifecycleEvents;
import net.fabricmc.loader.api.FabricLoader;
import net.minecraft.core.Registry;
import net.minecraft.core.registries.BuiltInRegistries;
import net.minecraft.world.level.storage.LevelResource;

public class BigOceansFabric implements ModInitializer {
    @Override
    public void onInitialize() {
        Registry.register(BuiltInRegistries.DENSITY_FUNCTION_TYPE, BigOceans.MOD_ID + ":" + BigOceans.OCEAN_BASINS, OceanBasinsFunction.CODEC.codec());
        ServerLifecycleEvents.SERVER_STARTING.register(server ->
                BigOceans.onServerStarting(server.getWorldPath(LevelResource.ROOT), FabricLoader.getInstance().getConfigDir()));
    }
}
