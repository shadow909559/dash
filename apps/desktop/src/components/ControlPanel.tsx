import React from 'react';
import { ColorPreset, GeometryCoreShape, HudSettings, RenderMode } from '../types';
import { COLOR_PRESETS } from '../constants';
import { Sliders, RotateCcw, Palette, Box, Activity, Eye, Layers, Sparkles, Volume2, X } from 'lucide-react';
import { soundFx } from '../utils/audio';

interface ControlPanelProps {
  settings: HudSettings;
  colorPreset: ColorPreset;
  onUpdateSettings: (updater: (prev: HudSettings) => HudSettings) => void;
  onResetDefaults: () => void;
  onClose: () => void;
}

export const ControlPanel: React.FC<ControlPanelProps> = ({
  settings,
  colorPreset,
  onUpdateSettings,
  onResetDefaults,
  onClose,
}) => {
  const handleColorSelect = (presetId: string) => {
    if (settings.soundEnabled) soundFx.playClick();
    onUpdateSettings((prev) => ({ ...prev, colorPresetId: presetId }));
  };

  const handleShapeSelect = (shape: GeometryCoreShape) => {
    if (settings.soundEnabled) soundFx.playClick();
    onUpdateSettings((prev) => ({ ...prev, coreShape: shape }));
  };

  const handleRenderModeSelect = (mode: RenderMode) => {
    if (settings.soundEnabled) soundFx.playClick();
    onUpdateSettings((prev) => ({ ...prev, renderMode: mode }));
  };

  const handleToggle = (key: keyof HudSettings) => {
    if (settings.soundEnabled) soundFx.playClick();
    onUpdateSettings((prev) => {
      const nextVal = !prev[key];
      if (key === 'ambientHum') {
        soundFx.toggleAmbientHum(nextVal);
      }
      return { ...prev, [key]: nextVal };
    });
  };

  return (
    <div className="pointer-events-auto absolute top-16 right-4 sm:right-6 z-30 w-80 sm:w-96 max-h-[calc(100vh-6rem)] overflow-y-auto bg-black/85 backdrop-blur-xl border border-white/15 rounded-md shadow-2xl p-4 font-mono text-xs text-white/90 flex flex-col gap-4 select-none scrollbar-thin scrollbar-thumb-white/20">
      {/* Panel Header */}
      <div className="flex items-center justify-between border-b border-white/15 pb-2">
        <div className="flex items-center gap-2">
          <Sliders className={`w-4 h-4 ${colorPreset.textClass}`} />
          <span className="font-bold tracking-widest text-sm text-white">HUD_SETTINGS_DECK</span>
        </div>
        <button
          onClick={() => {
            if (settings.soundEnabled) soundFx.playClick();
            onClose();
          }}
          className="text-white/50 hover:text-white p-1 rounded-sm hover:bg-white/10 transition-colors"
        >
          <X className="w-4 h-4" />
        </button>
      </div>

      {/* 1. COLOR THEME PRESETS */}
      <div className="flex flex-col gap-2">
        <label className="flex items-center gap-1.5 font-semibold text-white/70">
          <Palette className="w-3.5 h-3.5 text-white/50" />
          <span>COLOR PRESET</span>
        </label>
        <div className="grid grid-cols-3 gap-2">
          {COLOR_PRESETS.map((preset) => (
            <button
              key={preset.id}
              onClick={() => handleColorSelect(preset.id)}
              className={`flex flex-col items-center p-2 rounded-xs border transition-all duration-150 ${
                settings.colorPresetId === preset.id
                  ? `${preset.borderClass} bg-white/10 shadow-[0_0_10px_rgba(255,255,255,0.1)]`
                  : 'border-white/10 bg-black/40 hover:border-white/30 text-white/60'
              }`}
            >
              <span
                className="w-4 h-4 rounded-full mb-1 border border-white/30"
                style={{ backgroundColor: preset.hex }}
              />
              <span className="text-[9px] text-center font-medium line-clamp-1">{preset.name.split(' ')[0]}</span>
            </button>
          ))}
        </div>
      </div>

      {/* 2. CORE GEOMETRY SHAPE */}
      <div className="flex flex-col gap-2">
        <label className="flex items-center gap-1.5 font-semibold text-white/70">
          <Box className="w-3.5 h-3.5 text-white/50" />
          <span>CENTER CORE SHAPE</span>
        </label>
        <div className="grid grid-cols-3 gap-1.5">
          {(['sphere', 'icosahedron', 'octahedron', 'torusKnot', 'dodecahedron'] as GeometryCoreShape[]).map((shape) => (
            <button
              key={shape}
              onClick={() => handleShapeSelect(shape)}
              className={`py-1.5 px-2 rounded-xs border text-[10px] uppercase transition-all duration-150 ${
                settings.coreShape === shape
                  ? `${colorPreset.borderClass} bg-white/10 ${colorPreset.textClass} font-bold`
                  : 'border-white/10 bg-black/40 hover:border-white/30 text-white/60'
              }`}
            >
              {shape}
            </button>
          ))}
        </div>
      </div>

      {/* 3. RENDER MODE */}
      <div className="flex flex-col gap-2">
        <label className="flex items-center gap-1.5 font-semibold text-white/70">
          <Eye className="w-3.5 h-3.5 text-white/50" />
          <span>GEOMETRY RENDER MODE</span>
        </label>
        <div className="grid grid-cols-3 gap-1.5">
          {(['wireframe', 'solid', 'points'] as RenderMode[]).map((mode) => (
            <button
              key={mode}
              onClick={() => handleRenderModeSelect(mode)}
              className={`py-1.5 px-2 rounded-xs border text-[10px] uppercase transition-all duration-150 ${
                settings.renderMode === mode
                  ? `${colorPreset.borderClass} bg-white/10 ${colorPreset.textClass} font-bold`
                  : 'border-white/10 bg-black/40 hover:border-white/30 text-white/60'
              }`}
            >
              {mode}
            </button>
          ))}
        </div>
      </div>

      {/* 4. ANIMATION SLIDERS */}
      <div className="flex flex-col gap-3 border-t border-white/10 pt-3">
        {/* Rotation Speed */}
        <div className="flex flex-col gap-1">
          <div className="flex justify-between text-[11px]">
            <span className="text-white/70">ROTATION SPEED</span>
            <span className={colorPreset.textClass}>{settings.rotationSpeed.toFixed(1)}x</span>
          </div>
          <input
            type="range"
            min="0"
            max="3"
            step="0.1"
            value={settings.rotationSpeed}
            onChange={(e) => onUpdateSettings((prev) => ({ ...prev, rotationSpeed: parseFloat(e.target.value) }))}
            className="w-full accent-white h-1 bg-white/20 rounded-lg cursor-pointer"
          />
        </div>

        {/* Float Amplitude */}
        <div className="flex flex-col gap-1">
          <div className="flex justify-between text-[11px]">
            <span className="text-white/70">FLOAT AMPLITUDE</span>
            <span className={colorPreset.textClass}>{settings.floatAmplitude.toFixed(2)}m</span>
          </div>
          <input
            type="range"
            min="0"
            max="0.8"
            step="0.05"
            value={settings.floatAmplitude}
            onChange={(e) => onUpdateSettings((prev) => ({ ...prev, floatAmplitude: parseFloat(e.target.value) }))}
            className="w-full accent-white h-1 bg-white/20 rounded-lg cursor-pointer"
          />
        </div>

        {/* Camera Distance */}
        <div className="flex flex-col gap-1">
          <div className="flex justify-between text-[11px]">
            <span className="text-white/70">CAMERA DISTANCE</span>
            <span className={colorPreset.textClass}>{settings.cameraDistance.toFixed(1)}</span>
          </div>
          <input
            type="range"
            min="4"
            max="14"
            step="0.5"
            value={settings.cameraDistance}
            onChange={(e) => onUpdateSettings((prev) => ({ ...prev, cameraDistance: parseFloat(e.target.value) }))}
            className="w-full accent-white h-1 bg-white/20 rounded-lg cursor-pointer"
          />
        </div>
      </div>

      {/* 5. TOGGLES */}
      <div className="flex flex-col gap-2 border-t border-white/10 pt-3">
        <label className="font-semibold text-white/70 mb-1">HUD FEATURES & EFFECTS</label>

        <div className="grid grid-cols-2 gap-2 text-[10px]">
          <button
            onClick={() => handleToggle('showExtraRings')}
            className={`p-2 border rounded-xs flex items-center gap-1.5 transition-all ${
              settings.showExtraRings
                ? `${colorPreset.borderClass} bg-white/10 ${colorPreset.textClass}`
                : 'border-white/10 bg-black/40 text-white/50'
            }`}
          >
            <Layers className="w-3.5 h-3.5" />
            <span>EXTRA RINGS</span>
          </button>

          <button
            onClick={() => handleToggle('showParticles')}
            className={`p-2 border rounded-xs flex items-center gap-1.5 transition-all ${
              settings.showParticles
                ? `${colorPreset.borderClass} bg-white/10 ${colorPreset.textClass}`
                : 'border-white/10 bg-black/40 text-white/50'
            }`}
          >
            <Sparkles className="w-3.5 h-3.5" />
            <span>CYBER DUST</span>
          </button>

          <button
            onClick={() => handleToggle('showTargetLock')}
            className={`p-2 border rounded-xs flex items-center gap-1.5 transition-all ${
              settings.showTargetLock
                ? `${colorPreset.borderClass} bg-white/10 ${colorPreset.textClass}`
                : 'border-white/10 bg-black/40 text-white/50'
            }`}
          >
            <Activity className="w-3.5 h-3.5" />
            <span>TARGET LOCK</span>
          </button>

          <button
            onClick={() => handleToggle('autoRotate')}
            className={`p-2 border rounded-xs flex items-center gap-1.5 transition-all ${
              settings.autoRotate
                ? `${colorPreset.borderClass} bg-white/10 ${colorPreset.textClass}`
                : 'border-white/10 bg-black/40 text-white/50'
            }`}
          >
            <Activity className="w-3.5 h-3.5" />
            <span>AUTO ROTATE</span>
          </button>

          <button
            onClick={() => handleToggle('ambientHum')}
            className={`p-2 border rounded-xs flex items-center gap-1.5 col-span-2 transition-all ${
              settings.ambientHum
                ? `${colorPreset.borderClass} bg-white/10 ${colorPreset.textClass}`
                : 'border-white/10 bg-black/40 text-white/50'
            }`}
          >
            <Volume2 className="w-3.5 h-3.5" />
            <span>REACTOR AMBIENT HUM</span>
          </button>
        </div>
      </div>

      {/* Panel Footer: Reset Defaults */}
      <div className="border-t border-white/15 pt-3 flex justify-end">
        <button
          onClick={() => {
            if (settings.soundEnabled) soundFx.playClick();
            onResetDefaults();
          }}
          className="flex items-center gap-1.5 px-3 py-1.5 bg-red-950/60 hover:bg-red-900 border border-red-500/40 text-red-300 rounded-xs transition-colors text-[10px]"
        >
          <RotateCcw className="w-3 h-3" />
          <span>RESET DEFAULTS</span>
        </button>
      </div>
    </div>
  );
};
