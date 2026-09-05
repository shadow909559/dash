import React, { useEffect, useRef, useMemo } from 'react';
import * as THREE from 'three';
import { useAIStore } from '@/stores/aiStore';
import { DASH_COLORS, type DASHState } from '@/stores/dashState';
import { HudSettings } from '@/types';
import { EffectComposer } from 'three/examples/jsm/postprocessing/EffectComposer.js';
import { RenderPass } from 'three/examples/jsm/postprocessing/RenderPass.js';
import { UnrealBloomPass } from 'three/examples/jsm/postprocessing/UnrealBloomPass.js';

interface NeuralOrbProps {
  className?: string;
  settings: HudSettings;
}

// DASH State Colors - converted from CSS to THREE.Color
const STATE_COLORS: Record<DASHState, THREE.Color> = {
  idle: new THREE.Color(0x60a5fa),           // Soft blue
  listening: new THREE.Color(0xff9600),    // Orange + bright
  thinking: new THREE.Color(0xff8c00),      // Orange
  speaking: new THREE.Color(0xff9600),      // Orange
  coding: new THREE.Color(0x22c55e),        // Green
  researching: new THREE.Color(0x3b82f6),    // Blue
  debugging: new THREE.Color(0xa855f7),     // Purple
  executing: new THREE.Color(0xeab308),     // Dynamic gold
  success: new THREE.Color(0x22c55e),       // Green
  warning: new THREE.Color(0xef4444),       // Red-amber
  error: new THREE.Color(0xef4444),         // Red
  offline: new THREE.Color(0x6b7280),       // Gray-red
  connecting: new THREE.Color(0x3b82f6),    // Blue pulsing
  background: new THREE.Color(0x60a5fa),    // Dimmed
};

// Orb Animation Parameters
// Optimized for GTX 1650 4GB VRAM - reduced particle counts for GPU efficiency
const ORB_CONFIG = {
  baseRadius: 1.0,
  coreRadius: 0.4,
  outerRingRadius: 2.5,
  innerRingRadius: 1.8,
  particleCount: 800,  // Reduced from 2000 for GPU efficiency
  orbitingParticleCount: 50,  // Reduced from 100 for GPU efficiency
  floatAmplitude: 0.15,
  floatSpeed: 0.8,
  baseRotationSpeed: 0.005,
  transitionDuration: 0.6, // seconds
  targetFPS: 60,  // Cap at 60 FPS for consistent performance
};

export const NeuralOrb: React.FC<NeuralOrbProps> = ({ className = '', settings }) => {
  const containerRef = useRef<HTMLDivElement>(null);
  const sceneRef = useRef<THREE.Scene | null>(null);
  const rendererRef = useRef<THREE.WebGLRenderer | null>(null);
  const cameraRef = useRef<THREE.PerspectiveCamera | null>(null);
  
  // Orb components
  const coreGroupRef = useRef<THREE.Group | null>(null);
  const ringsGroupRef = useRef<THREE.Group | null>(null);
  const particlesGroupRef = useRef<THREE.Group | null>(null);
  const outerRingRef = useRef<THREE.Mesh | null>(null);
  const innerRingRef = useRef<THREE.Mesh | null>(null);
  const coreSphereRef = useRef<THREE.Mesh | null>(null);
  const energyFieldRef = useRef<THREE.Mesh | null>(null);
  
  // Particle systems
  const ambientParticlesRef = useRef<THREE.Points | null>(null);
  const orbitingParticlesRef = useRef<THREE.Points | null>(null);
  const energyArcsRef = useRef<THREE.LineSegments | null>(null);
  
  // Animation state
  const animFrameIdRef = useRef<number | null>(null);
  const timeRef = useRef(0);
  const lastFrameTimeRef = useRef(0);
  const currentColorRef = useRef(STATE_COLORS.idle.clone());
  const targetColorRef = useRef(STATE_COLORS.idle.clone());
  const transitionStartTimeRef = useRef(0);
  const isTransitioningRef = useRef(false);
  
  // Post-processing
  const composerRef = useRef<EffectComposer | null>(null);
  const bloomPassRef = useRef<UnrealBloomPass | null>(null);
  
  // Voice/mic amplitude
  const voiceAmplitudeRef = useRef(0);
  const micAmplitudeRef = useRef(0);
  
  // Emotion parameters
  const emotionParamsRef = useRef({
    rotationSpeed: 1.0,
    floatAmplitude: 0.15,
    floatSpeed: 0.8,
    pulseIntensity: 0.5,
    particleSpeed: 1.0,
    glowIntensity: 0.6,
    energyFlow: 0.5,
  });
  
  // Store integration
  const { dashState, emotion, setAIState } = useAIStore();

  // Initialize Three.js scene
  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    const width = container.clientWidth || window.innerWidth;
    const height = container.clientHeight || window.innerHeight;

    // Scene setup
    const scene = new THREE.Scene();
    sceneRef.current = scene;

    // Camera
    const camera = new THREE.PerspectiveCamera(75, width / height, 0.1, 1000);
    camera.position.z = 5;
    cameraRef.current = camera;

    // Renderer with optimizations
    const renderer = new THREE.WebGLRenderer({ 
      alpha: true, 
      antialias: true,
      powerPreference: 'high-performance',
    });
    renderer.setSize(width, height);
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    renderer.toneMapping = THREE.ACESFilmicToneMapping;
    renderer.toneMappingExposure = 1.2;
    container.appendChild(renderer.domElement);
    rendererRef.current = renderer;

    // Post-processing setup
    const composer = new EffectComposer(renderer);
    const renderPass = new RenderPass(scene, camera);
    composer.addPass(renderPass);

    // Bloom pass for glow effect
    const bloomPass = new UnrealBloomPass(
      new THREE.Vector2(width, height),
      1.5,  // strength
      0.4,  // radius
      0.85  // threshold
    );
    composer.addPass(bloomPass);
    bloomPassRef.current = bloomPass;

    composerRef.current = composer;

    // Create orb structure
    createOrbStructure(scene);

    // Start animation loop
    animate();

    // Handle resize
    const handleResize = () => {
      const w = container.clientWidth || window.innerWidth;
      const h = container.clientHeight || window.innerHeight;
      camera.aspect = w / h;
      camera.updateProjectionMatrix();
      renderer.setSize(w, h);
      composer.setSize(w, h);
    };
    window.addEventListener('resize', handleResize);

    return () => {
      window.removeEventListener('resize', handleResize);
      if (animFrameIdRef.current) {
        cancelAnimationFrame(animFrameIdRef.current);
      }
      container.removeChild(renderer.domElement);
      renderer.dispose();
    };
  }, []);

  // Create orb structure with all components
  const createOrbStructure = (scene: THREE.Scene) => {
    // Main orb group
    const orbGroup = new THREE.Group();
    scene.add(orbGroup);

    // Core group (contains the actual AI core)
    const coreGroup = new THREE.Group();
    orbGroup.add(coreGroup);
    coreGroupRef.current = coreGroup;

    // Rings group (rotating rings)
    const ringsGroup = new THREE.Group();
    orbGroup.add(ringsGroup);
    ringsGroupRef.current = ringsGroup;

    // Particles group
    const particlesGroup = new THREE.Group();
    orbGroup.add(particlesGroup);
    particlesGroupRef.current = particlesGroup;

    // 1. Core Sphere (glowing energy center)
    const coreGeometry = new THREE.SphereGeometry(ORB_CONFIG.coreRadius, 64, 64);
    const coreMaterial = new THREE.ShaderMaterial({
      uniforms: {
        time: { value: 0 },
        color: { value: currentColorRef.current },
        amplitude: { value: 0 },
      },
      vertexShader: `
        uniform float time;
        uniform float amplitude;
        varying vec3 vNormal;
        varying vec3 vPosition;
        
        void main() {
          vNormal = normal;
          vPosition = position;
          
          // Breathing effect
          vec3 pos = position;
          float breathe = sin(time * 2.0) * 0.05 * amplitude;
          pos += normal * breathe;
          
          gl_Position = projectionMatrix * modelViewMatrix * vec4(pos, 1.0);
        }
      `,
      fragmentShader: `
        uniform float time;
        uniform vec3 color;
        uniform float amplitude;
        varying vec3 vNormal;
        varying vec3 vPosition;
        
        void main() {
          // Fresnel effect for glowing edge
          vec3 viewDir = normalize(cameraPosition - vPosition);
          float fresnel = pow(1.0 - dot(viewDir, vNormal), 3.0);
          
          // Pulsing core
          float pulse = sin(time * 3.0) * 0.3 + 0.7;
          float intensity = fresnel * pulse * (1.0 + amplitude);
          
          vec3 finalColor = color * intensity;
          gl_FragColor = vec4(finalColor, 0.9);
        }
      `,
      transparent: true,
      blending: THREE.AdditiveBlending,
    });
    const coreSphere = new THREE.Mesh(coreGeometry, coreMaterial);
    coreGroup.add(coreSphere);
    coreSphereRef.current = coreSphere;

    // 2. Energy Field (outer glow)
    const energyGeometry = new THREE.SphereGeometry(ORB_CONFIG.baseRadius * 1.5, 32, 32);
    const energyMaterial = new THREE.ShaderMaterial({
      uniforms: {
        time: { value: 0 },
        color: { value: currentColorRef.current },
        amplitude: { value: 0 },
      },
      vertexShader: `
        uniform float time;
        varying vec3 vNormal;
        varying vec2 vUv;
        
        void main() {
          vNormal = normal;
          vUv = uv;
          gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
        }
      `,
      fragmentShader: `
        uniform float time;
        uniform vec3 color;
        uniform float amplitude;
        varying vec3 vNormal;
        varying vec2 vUv;
        
        void main() {
          // Energy ripple effect
          float ripple = sin(vUv.y * 20.0 - time * 5.0) * 0.5 + 0.5;
          float intensity = ripple * 0.3 * (1.0 + amplitude * 0.5);
          
          vec3 finalColor = color * intensity;
          gl_FragColor = vec4(finalColor, 0.3);
        }
      `,
      transparent: true,
      blending: THREE.AdditiveBlending,
      side: THREE.BackSide,
    });
    const energyField = new THREE.Mesh(energyGeometry, energyMaterial);
    coreGroup.add(energyField);
    energyFieldRef.current = energyField;

    // 3. Outer Ring (rotating holographic ring)
    const outerRingGeometry = new THREE.TorusGeometry(ORB_CONFIG.outerRingRadius, 0.02, 16, 100);
    const outerRingMaterial = new THREE.ShaderMaterial({
      uniforms: {
        time: { value: 0 },
        color: { value: currentColorRef.current },
        amplitude: { value: 0 },
      },
      vertexShader: `
        uniform float time;
        uniform float amplitude;
        varying vec2 vUv;
        
        void main() {
          vUv = uv;
          vec3 pos = position;
          
          // Subtle ring expansion with amplitude
          float expansion = sin(time * 2.0) * 0.05 * amplitude;
          pos += normal * expansion;
          
          gl_Position = projectionMatrix * modelViewMatrix * vec4(pos, 1.0);
        }
      `,
      fragmentShader: `
        uniform float time;
        uniform vec3 color;
        uniform float amplitude;
        varying vec2 vUv;
        
        void main() {
          // Scanning effect
          float scan = sin(vUv.x * 10.0 - time * 3.0) * 0.5 + 0.5;
          float intensity = scan * (0.8 + amplitude * 0.2);
          
          vec3 finalColor = color * intensity;
          gl_FragColor = vec4(finalColor, 0.6);
        }
      `,
      transparent: true,
      blending: THREE.AdditiveBlending,
    });
    const outerRing = new THREE.Mesh(outerRingGeometry, outerRingMaterial);
    outerRing.rotation.x = Math.PI / 2;
    ringsGroup.add(outerRing);
    outerRingRef.current = outerRing;

    // 4. Inner Ring (counter-rotating)
    const innerRingGeometry = new THREE.TorusGeometry(ORB_CONFIG.innerRingRadius, 0.015, 16, 80);
    const innerRingMaterial = new THREE.ShaderMaterial({
      uniforms: {
        time: { value: 0 },
        color: { value: currentColorRef.current },
        amplitude: { value: 0 },
      },
      vertexShader: `
        uniform float time;
        uniform float amplitude;
        varying vec2 vUv;
        
        void main() {
          vUv = uv;
          vec3 pos = position;
          float expansion = sin(time * 2.5) * 0.03 * amplitude;
          pos += normal * expansion;
          gl_Position = projectionMatrix * modelViewMatrix * vec4(pos, 1.0);
        }
      `,
      fragmentShader: `
        uniform float time;
        uniform vec3 color;
        uniform float amplitude;
        varying vec2 vUv;
        
        void main() {
          float pulse = sin(vUv.x * 15.0 + time * 4.0) * 0.5 + 0.5;
          float intensity = pulse * (0.6 + amplitude * 0.3);
          vec3 finalColor = color * intensity;
          gl_FragColor = vec4(finalColor, 0.5);
        }
      `,
      transparent: true,
      blending: THREE.AdditiveBlending,
    });
    const innerRing = new THREE.Mesh(innerRingGeometry, innerRingMaterial);
    innerRing.rotation.x = Math.PI / 2;
    innerRing.rotation.y = Math.PI / 4;
    ringsGroup.add(innerRing);
    innerRingRef.current = innerRing;

    // 5. Ambient Particles (GPU particles)
    const ambientParticles = createGPUParticles(ORB_CONFIG.particleCount, 'ambient');
    particlesGroup.add(ambientParticles);
    ambientParticlesRef.current = ambientParticles;

    // 6. Orbiting Particles
    const orbitingParticles = createGPUParticles(ORB_CONFIG.orbitingParticleCount, 'orbiting');
    particlesGroup.add(orbitingParticles);
    orbitingParticlesRef.current = orbitingParticles;

    // 7. Energy Arcs (dynamic energy streams)
    const energyArcs = createEnergyArcs();
    particlesGroup.add(energyArcs);
    energyArcsRef.current = energyArcs as THREE.LineSegments;
  };

  // Create GPU particle system
  const createGPUParticles = (count: number, type: 'ambient' | 'orbiting') => {
    const positions = new Float32Array(count * 3);
    const velocities = new Float32Array(count * 3);
    const sizes = new Float32Array(count);

    for (let i = 0; i < count; i++) {
      if (type === 'ambient') {
        // Ambient particles - random distribution around orb
        const theta = Math.random() * Math.PI * 2;
        const phi = Math.random() * Math.PI;
        const radius = ORB_CONFIG.baseRadius * 1.5 + Math.random() * 2;
        
        positions[i * 3] = radius * Math.sin(phi) * Math.cos(theta);
        positions[i * 3 + 1] = radius * Math.sin(phi) * Math.sin(theta);
        positions[i * 3 + 2] = radius * Math.cos(phi);
        
        velocities[i * 3] = (Math.random() - 0.5) * 0.01;
        velocities[i * 3 + 1] = (Math.random() - 0.5) * 0.01;
        velocities[i * 3 + 2] = (Math.random() - 0.5) * 0.01;
      } else {
        // Orbiting particles - circular orbits
        const angle = (i / count) * Math.PI * 2;
        const radius = ORB_CONFIG.outerRingRadius + Math.random() * 0.5;
        
        positions[i * 3] = Math.cos(angle) * radius;
        positions[i * 3 + 1] = Math.sin(angle) * radius;
        positions[i * 3 + 2] = (Math.random() - 0.5) * 0.5;
        
        velocities[i * 3] = -Math.sin(angle) * 0.02;
        velocities[i * 3 + 1] = Math.cos(angle) * 0.02;
        velocities[i * 3 + 2] = 0;
      }
      
      sizes[i] = Math.random() * 2 + 1;
    }

    const geometry = new THREE.BufferGeometry();
    geometry.setAttribute('position', new THREE.BufferAttribute(positions, 3));
    geometry.setAttribute('velocity', new THREE.BufferAttribute(velocities, 3));
    geometry.setAttribute('size', new THREE.BufferAttribute(sizes, 1));

    const material = new THREE.ShaderMaterial({
      uniforms: {
        time: { value: 0 },
        color: { value: currentColorRef.current },
        amplitude: { value: 0 },
      },
      vertexShader: `
        uniform float time;
        uniform float amplitude;
        attribute vec3 velocity;
        attribute float size;
        varying float vAlpha;
        
        void main() {
          vec3 pos = position;
          
          // Move particles
          pos += velocity * time * 10.0;
          
          // React to amplitude
          if (amplitude > 0.1) {
            pos += normal * amplitude * 0.2;
          }
          
          vec4 mvPosition = modelViewMatrix * vec4(pos, 1.0);
          gl_PointSize = size * (300.0 / -mvPosition.z);
          gl_Position = projectionMatrix * mvPosition;
          
          vAlpha = 0.6 + sin(time * 2.0 + position.x) * 0.2;
        }
      `,
      fragmentShader: `
        uniform vec3 color;
        uniform float amplitude;
        varying float vAlpha;
        
        void main() {
          float dist = length(gl_PointCoord - vec2(0.5));
          if (dist > 0.5) discard;
          
          float alpha = (1.0 - dist * 2.0) * vAlpha * (1.0 + amplitude);
          vec3 finalColor = color * (1.0 + amplitude * 0.5);
          gl_FragColor = vec4(finalColor, alpha);
        }
      `,
      transparent: true,
      blending: THREE.AdditiveBlending,
      depthWrite: false,
    });

    return new THREE.Points(geometry, material);
  };

  // Create energy arcs
  const createEnergyArcs = () => {
    const arcCount = 20;
    const positions = new Float32Array(arcCount * 6); // 2 points per arc
    const colors = new Float32Array(arcCount * 6);

    for (let i = 0; i < arcCount; i++) {
      const angle = (i / arcCount) * Math.PI * 2;
      const radius = ORB_CONFIG.baseRadius * 1.2;
      
      positions[i * 6] = Math.cos(angle) * radius;
      positions[i * 6 + 1] = Math.sin(angle) * radius;
      positions[i * 6 + 2] = 0;
      
      positions[i * 6 + 3] = Math.cos(angle + 0.2) * radius * 1.1;
      positions[i * 6 + 4] = Math.sin(angle + 0.2) * radius * 1.1;
      positions[i * 6 + 5] = 0;
      
      colors[i * 6] = 1;
      colors[i * 6 + 1] = 1;
      colors[i * 6 + 2] = 1;
      colors[i * 6 + 3] = 1;
      colors[i * 6 + 4] = 1;
      colors[i * 6 + 5] = 1;
    }

    const geometry = new THREE.BufferGeometry();
    geometry.setAttribute('position', new THREE.BufferAttribute(positions, 3));
    geometry.setAttribute('color', new THREE.BufferAttribute(colors, 3));

    const material = new THREE.ShaderMaterial({
      uniforms: {
        time: { value: 0 },
        color: { value: currentColorRef.current },
        amplitude: { value: 0 },
      },
      vertexShader: `
        uniform float time;
        uniform float amplitude;
        varying vec2 vUv;
        
        void main() {
          vUv = uv;
          vec3 pos = position;
          
          // Energy flow
          float flow = sin(time * 5.0 + position.x) * 0.05 * amplitude;
          pos += normal * flow;
          
          gl_Position = projectionMatrix * modelViewMatrix * vec4(pos, 1.0);
        }
      `,
      fragmentShader: `
        uniform float time;
        uniform vec3 color;
        uniform float amplitude;
        varying vec2 vUv;
        
        void main() {
          float energy = sin(vUv.x * 10.0 - time * 8.0) * 0.5 + 0.5;
          float intensity = energy * (0.8 + amplitude * 0.4);
          vec3 finalColor = color * intensity;
          gl_FragColor = vec4(finalColor, 0.4);
        }
      `,
      transparent: true,
      blending: THREE.AdditiveBlending,
    });

    return new THREE.LineSegments(geometry, material);
  };

  // Update orb color based on AI state
  const updateOrbColor = (deltaTime: number) => {
    const targetColor = STATE_COLORS[dashState as keyof typeof STATE_COLORS] || STATE_COLORS.idle;
    
    if (!targetColorRef.current.equals(targetColor)) {
      targetColorRef.current.copy(targetColor);
      transitionStartTimeRef.current = timeRef.current;
      isTransitioningRef.current = true;
    }

    if (isTransitioningRef.current) {
      const elapsed = timeRef.current - transitionStartTimeRef.current;
      const progress = Math.min(elapsed / ORB_CONFIG.transitionDuration, 1.0);
      
      // Smooth interpolation
      currentColorRef.current.lerp(targetColorRef.current, progress * deltaTime * 3);
      
      if (progress >= 1.0) {
        isTransitioningRef.current = false;
      }
    }

    // Update all shader uniforms
    if (coreSphereRef.current) {
      (coreSphereRef.current.material as THREE.ShaderMaterial).uniforms.color.value.copy(currentColorRef.current);
    }
    if (energyFieldRef.current) {
      (energyFieldRef.current.material as THREE.ShaderMaterial).uniforms.color.value.copy(currentColorRef.current);
    }
    if (outerRingRef.current) {
      (outerRingRef.current.material as THREE.ShaderMaterial).uniforms.color.value.copy(currentColorRef.current);
    }
    if (innerRingRef.current) {
      (innerRingRef.current.material as THREE.ShaderMaterial).uniforms.color.value.copy(currentColorRef.current);
    }
    if (ambientParticlesRef.current) {
      (ambientParticlesRef.current.material as THREE.ShaderMaterial).uniforms.color.value.copy(currentColorRef.current);
    }
    if (orbitingParticlesRef.current) {
      (orbitingParticlesRef.current.material as THREE.ShaderMaterial).uniforms.color.value.copy(currentColorRef.current);
    }
    if (energyArcsRef.current) {
      (energyArcsRef.current.material as THREE.ShaderMaterial).uniforms.color.value.copy(currentColorRef.current);
    }
  };

  // Update amplitude based on voice/mic input
  const updateAmplitude = () => {
    let targetAmplitude = 0;

    if (dashState === 'speaking') {
      targetAmplitude = voiceAmplitudeRef.current;
    } else if (dashState === 'listening') {
      targetAmplitude = micAmplitudeRef.current;
    }
    
    // Smooth amplitude transition
    const smoothAmplitude = THREE.MathUtils.lerp(
      (coreSphereRef.current?.material as THREE.ShaderMaterial).uniforms.amplitude.value,
      targetAmplitude,
      0.1
    );
    
    if (coreSphereRef.current) {
      (coreSphereRef.current.material as THREE.ShaderMaterial).uniforms.amplitude.value = smoothAmplitude;
    }
    if (energyFieldRef.current) {
      (energyFieldRef.current.material as THREE.ShaderMaterial).uniforms.amplitude.value = smoothAmplitude;
    }
    if (outerRingRef.current) {
      (outerRingRef.current.material as THREE.ShaderMaterial).uniforms.amplitude.value = smoothAmplitude;
    }
    if (innerRingRef.current) {
      (innerRingRef.current.material as THREE.ShaderMaterial).uniforms.amplitude.value = smoothAmplitude;
    }
  };

  // Main animation loop
  const animate = () => {
    const now = performance.now() / 1000;
    const deltaTime = now - timeRef.current;
    timeRef.current = now;

    // FPS capping for GTX 1650 optimization
    const frameInterval = 1000 / ORB_CONFIG.targetFPS;
    const elapsedSinceLastFrame = now - lastFrameTimeRef.current;
    if (elapsedSinceLastFrame < frameInterval / 1000) {
      animFrameIdRef.current = requestAnimationFrame(animate);
      return;
    }
    lastFrameTimeRef.current = now;

    // Performance: Skip rendering if window is hidden
    if (document.hidden) {
      animFrameIdRef.current = requestAnimationFrame(animate);
      return;
    }

    if (!rendererRef.current || !sceneRef.current || !cameraRef.current) return;

    // Update emotion parameters from global state
    if ((window as any).orbEmotionParams) {
      emotionParamsRef.current = (window as any).orbEmotionParams;
    }

    // Update time uniforms
    const timeUniform = { value: now };
    
    if (coreSphereRef.current) {
      (coreSphereRef.current.material as THREE.ShaderMaterial).uniforms.time.value = now;
    }
    if (energyFieldRef.current) {
      (energyFieldRef.current.material as THREE.ShaderMaterial).uniforms.time.value = now;
    }
    if (outerRingRef.current) {
      (outerRingRef.current.material as THREE.ShaderMaterial).uniforms.time.value = now;
    }
    if (innerRingRef.current) {
      (innerRingRef.current.material as THREE.ShaderMaterial).uniforms.time.value = now;
    }
    if (ambientParticlesRef.current) {
      (ambientParticlesRef.current.material as THREE.ShaderMaterial).uniforms.time.value = now;
    }
    if (orbitingParticlesRef.current) {
      (orbitingParticlesRef.current.material as THREE.ShaderMaterial).uniforms.time.value = now;
    }
    if (energyArcsRef.current) {
      (energyArcsRef.current.material as THREE.ShaderMaterial).uniforms.time.value = now;
    }

    // Update colors
    updateOrbColor(deltaTime);

    // Update amplitude
    updateAmplitude();

    // Rotate rings independently with emotion-based speed
    if (ringsGroupRef.current) {
      ringsGroupRef.current.rotation.z += ORB_CONFIG.baseRotationSpeed * settings.rotationSpeed * emotionParamsRef.current.rotationSpeed;
    }
    if (outerRingRef.current) {
      outerRingRef.current.rotation.z += 0.002 * settings.rotationSpeed * emotionParamsRef.current.rotationSpeed;
    }
    if (innerRingRef.current) {
      innerRingRef.current.rotation.z -= 0.003 * settings.rotationSpeed * emotionParamsRef.current.rotationSpeed;
    }

    // Floating motion with emotion-based amplitude and speed
    if (coreGroupRef.current) {
      const floatY = Math.sin(now * ORB_CONFIG.floatSpeed * emotionParamsRef.current.floatSpeed) * ORB_CONFIG.floatAmplitude * emotionParamsRef.current.floatAmplitude;
      const floatX = Math.cos(now * ORB_CONFIG.floatSpeed * emotionParamsRef.current.floatSpeed * 0.7) * ORB_CONFIG.floatAmplitude * emotionParamsRef.current.floatAmplitude * 0.5;
      coreGroupRef.current.position.y = floatY;
      coreGroupRef.current.position.x = floatX;
    }

    // Rotate particles group with emotion-based speed
    if (particlesGroupRef.current) {
      particlesGroupRef.current.rotation.y += 0.001 * emotionParamsRef.current.particleSpeed;
    }

    // Update bloom intensity based on emotion
    if (bloomPassRef.current) {
      const targetBloomStrength = 1.5 * emotionParamsRef.current.glowIntensity;
      bloomPassRef.current.strength = THREE.MathUtils.lerp(
        bloomPassRef.current.strength,
        targetBloomStrength,
        0.05
      );
    }

    // Render
    if (composerRef.current) {
      composerRef.current.render();
    } else {
      rendererRef.current.render(sceneRef.current, cameraRef.current);
    }

    animFrameIdRef.current = requestAnimationFrame(animate);
  };

  // Expose amplitude setters for external use
  useEffect(() => {
    (window as any).setVoiceAmplitude = (amplitude: number) => {
      voiceAmplitudeRef.current = amplitude;
    };
    (window as any).setMicAmplitude = (amplitude: number) => {
      micAmplitudeRef.current = amplitude;
    };
    
    return () => {
      delete (window as any).setVoiceAmplitude;
      delete (window as any).setMicAmplitude;
    };
  }, []);

  return (
    <div 
      ref={containerRef} 
      className={`absolute inset-0 ${className}`}
      style={{ pointerEvents: 'none' }}
    />
  );
};
