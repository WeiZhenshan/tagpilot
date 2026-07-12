<template>
  <button
    class="weather-toggle"
    :class="{
      'is-checked': isChecked,
      'is-disabled': disabled,
      'is-animating': isAnimating
    }"
    type="button"
    role="switch"
    :aria-checked="String(isChecked)"
    :aria-label="ariaLabel"
    :title="stateTitle"
    :disabled="disabled"
    @click="toggle"
  >
    <span class="weather-toggle__weather-layer" :style="currentLayerStyle" aria-hidden="true">
      <img
        class="weather-toggle__frame"
        :src="frames[blend.from]"
        alt=""
        draggable="false"
        :style="frameImageStyles[blend.from]"
      >
      <span class="weather-toggle__thumb-cover" :style="frameCoverStyles[blend.from]"></span>
    </span>
    <span class="weather-toggle__weather-layer" :style="nextLayerStyle" aria-hidden="true">
      <img
        class="weather-toggle__frame"
        :src="frames[blend.to]"
        alt=""
        draggable="false"
        :style="frameImageStyles[blend.to]"
      >
      <span class="weather-toggle__thumb-cover" :style="frameCoverStyles[blend.to]"></span>
    </span>
    <span
      class="weather-toggle__transition-light"
      :style="{ opacity: transitionLightOpacity }"
      aria-hidden="true"
    ></span>
    <span
      class="weather-toggle__thumb"
      :style="thumbStyle"
      aria-hidden="true"
    ></span>
    <span class="weather-toggle__state">{{ stateTitle }}</span>
  </button>
</template>

<script>
import frame1 from "../../../../resources/images/weather_toggle_frames/weather_toggle_frame_1.png"
import frame2 from "../../../../resources/images/weather_toggle_frames/weather_toggle_frame_2.png"
import frame3 from "../../../../resources/images/weather_toggle_frames/weather_toggle_frame_3.png"
import frame4 from "../../../../resources/images/weather_toggle_frames/weather_toggle_frame_4.png"
import frame5 from "../../../../resources/images/weather_toggle_frames/weather_toggle_frame_5.png"
import frame6 from "../../../../resources/images/weather_toggle_frames/weather_toggle_frame_6.png"

const FRAME_STOPS = [0, 0.17, 0.35, 0.58, 0.8, 1]
const TARGET_TRACK_WIDTH = 40
const TARGET_TRACK_HEIGHT = 20
const FRAME_REGISTRATION = [
  { trackX: 77, trackY: 61, trackWidth: 350, trackHeight: 133, thumbX: 148, thumbY: 125, thumbRadius: 61, cover: "#334258" },
  { trackX: 68, trackY: 61, trackWidth: 354, trackHeight: 133, thumbX: 133, thumbY: 127, thumbRadius: 56, cover: "#34465e" },
  { trackX: 53, trackY: 62, trackWidth: 361, trackHeight: 131, thumbX: 117, thumbY: 125, thumbRadius: 54, cover: "#315373" },
  { trackX: 68, trackY: 48, trackWidth: 369, trackHeight: 137, thumbX: 308, thumbY: 112, thumbRadius: 55, cover: "#1c96f6" },
  { trackX: 57, trackY: 47, trackWidth: 365, trackHeight: 127, thumbX: 358, thumbY: 109, thumbRadius: 54, cover: "#168ff5" },
  { trackX: 53, trackY: 47, trackWidth: 369, trackHeight: 127, thumbX: 356, thumbY: 107, thumbRadius: 54, cover: "#168ff5" }
]

function clamp(value, min, max) {
  return Math.min(Math.max(value, min), max)
}

function smoothstep(edge0, edge1, value) {
  const progress = clamp((value - edge0) / (edge1 - edge0), 0, 1)
  return progress * progress * (3 - 2 * progress)
}

function easeInOutCubic(value) {
  return value < 0.5
    ? 4 * value * value * value
    : 1 - Math.pow(-2 * value + 2, 3) / 2
}

export default {
  name: "WeatherToggle",
  props: {
    value: {
      required: true
    },
    activeValue: {
      type: [String, Number, Boolean],
      default: true
    },
    inactiveValue: {
      type: [String, Number, Boolean],
      default: false
    },
    activeText: {
      type: String,
      default: "启用"
    },
    inactiveText: {
      type: String,
      default: "停用"
    },
    ariaLabel: {
      type: String,
      default: "状态切换"
    },
    disabled: {
      type: Boolean,
      default: false
    }
  },
  data() {
    const initialProgress = this.value === this.activeValue ? 1 : 0
    return {
      frames: [frame1, frame2, frame3, frame4, frame5, frame6],
      progress: initialProgress,
      animationFrameId: null,
      reduceMotion: false,
      isAnimating: false
    }
  },
  computed: {
    isChecked() {
      return this.value === this.activeValue
    },
    stateTitle() {
      return this.isChecked ? this.activeText : this.inactiveText
    },
    blend() {
      const progress = clamp(this.progress, 0, 1)
      if (progress >= 1) {
        return { from: 5, to: 5, mix: 0 }
      }

      let from = 0
      for (let index = 0; index < FRAME_STOPS.length - 1; index++) {
        if (progress >= FRAME_STOPS[index] && progress < FRAME_STOPS[index + 1]) {
          from = index
          break
        }
      }

      const start = FRAME_STOPS[from]
      const end = FRAME_STOPS[from + 1]
      const localProgress = (progress - start) / (end - start)
      return {
        from,
        to: Math.min(from + 1, 5),
        mix: smoothstep(0.2, 0.8, localProgress)
      }
    },
    currentLayerStyle() {
      return { opacity: 1 - this.blend.mix }
    },
    nextLayerStyle() {
      return { opacity: this.blend.mix }
    },
    frameMetrics() {
      return FRAME_REGISTRATION.map(frame => {
        const scaleX = TARGET_TRACK_WIDTH / frame.trackWidth
        const scaleY = TARGET_TRACK_HEIGHT / frame.trackHeight
        return {
          scaleX,
          scaleY,
          left: -frame.trackX * scaleX,
          top: -frame.trackY * scaleY,
          width: 500 * scaleX,
          height: 250 * scaleY
        }
      })
    },
    frameImageStyles() {
      return this.frameMetrics.map(frame => ({
        left: `${frame.left}px`,
        top: `${frame.top}px`,
        width: `${frame.width}px`,
        height: `${frame.height}px`
      }))
    },
    frameCoverStyles() {
      return FRAME_REGISTRATION.map((frame, index) => {
        const metrics = this.frameMetrics[index]
        const centerX = metrics.left + frame.thumbX * metrics.scaleX
        const centerY = metrics.top + frame.thumbY * metrics.scaleY
        // 素材圆钮经过横纵缩放后会成为椭圆；使用较大半径生成正圆遮罩，
        // 同时覆盖素材自带的深色圆环，只保留上层唯一的标准圆钮。
        const sourceRingRadius = frame.thumbRadius + 8
        const coverRadius = Math.max(
          sourceRingRadius * metrics.scaleX,
          sourceRingRadius * metrics.scaleY,
          TARGET_TRACK_HEIGHT / 2
        )
        return {
          left: `${centerX - coverRadius}px`,
          top: `${centerY - coverRadius}px`,
          width: `${coverRadius * 2}px`,
          height: `${coverRadius * 2}px`,
          background: frame.cover
        }
      })
    },
    thumbStyle() {
      const motion = Math.sin(Math.PI * this.progress)
      const translateX = this.progress * 20
      const scaleX = 1 + motion * 0.06
      const scaleY = 1 - motion * 0.03
      return {
        transform: `translate3d(${translateX}px, 0, 0) scaleX(${scaleX}) scaleY(${scaleY})`
      }
    },
    transitionLightOpacity() {
      return Math.sin(Math.PI * this.progress) * 0.14
    }
  },
  watch: {
    value() {
      this.animateTo(this.isChecked ? 1 : 0)
    }
  },
  mounted() {
    this.reduceMotion = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches
    this.preloadFrames()
  },
  beforeDestroy() {
    this.stopAnimation()
  },
  methods: {
    toggle() {
      if (this.disabled) {
        return
      }
      const nextValue = this.isChecked ? this.inactiveValue : this.activeValue
      this.$emit("input", nextValue)
      this.$emit("change", nextValue)
    },
    animateTo(target) {
      this.stopAnimation()
      if (this.reduceMotion) {
        this.progress = target
        return
      }

      const startProgress = this.progress
      const distance = target - startProgress
      if (Math.abs(distance) < 0.001) {
        this.progress = target
        return
      }

      const duration = Math.max(100, 280 * Math.abs(distance))
      const startTime = performance.now()
      this.isAnimating = true

      const update = currentTime => {
        const timeRatio = clamp((currentTime - startTime) / duration, 0, 1)
        this.progress = startProgress + distance * easeInOutCubic(timeRatio)

        if (timeRatio < 1) {
          this.animationFrameId = window.requestAnimationFrame(update)
        } else {
          this.progress = target
          this.animationFrameId = null
          this.isAnimating = false
        }
      }

      this.animationFrameId = window.requestAnimationFrame(update)
    },
    stopAnimation() {
      if (this.animationFrameId !== null) {
        window.cancelAnimationFrame(this.animationFrameId)
        this.animationFrameId = null
      }
      this.isAnimating = false
    },
    preloadFrames() {
      this.frames.forEach(src => {
        const image = new Image()
        image.src = src
        if (typeof image.decode === "function") {
          image.decode().catch(() => {})
        }
      })
    }
  }
}
</script>

<style lang="scss" scoped>
.weather-toggle {
  position: relative;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 40px;
  height: 20px;
  padding: 0;
  overflow: hidden;
  vertical-align: middle;
  cursor: pointer;
  background: #f4f6f9;
  border: 0;
  border-radius: 10px;
  outline: none;
  -webkit-tap-highlight-color: transparent;
  isolation: isolate;
  contain: paint;
  transform: translateZ(0);

  &:hover:not(.is-disabled) {
    filter: brightness(1.02);
  }

  &:active:not(.is-disabled) {
    transform: scale(0.97);
  }

  &:focus-visible {
    box-shadow: 0 0 0 2px #ffffff, 0 0 0 4px #1890ff;
  }

  &.is-disabled {
    cursor: not-allowed;
    filter: grayscale(0.3);
    opacity: 0.58;
  }
}

.weather-toggle__weather-layer {
  position: absolute;
  z-index: 1;
  display: block;
  inset: 0;
  pointer-events: none;
  transform: translateZ(0);
  will-change: opacity;
}

.weather-toggle__frame {
  position: absolute;
  top: 0;
  left: 0;
  display: block;
  max-width: none;
  pointer-events: none;
  user-select: none;
  object-fit: fill;
  backface-visibility: hidden;
  transform: translateZ(0);
}

.weather-toggle__thumb-cover {
  position: absolute;
  pointer-events: none;
  border-radius: 50%;
  transform: translateZ(0);
}

.weather-toggle__transition-light {
  position: absolute;
  z-index: 3;
  inset: 2px;
  pointer-events: none;
  background: linear-gradient(90deg, transparent 15%, rgba(255, 255, 255, 0.35) 50%, transparent 85%);
  border-radius: 8px;
  transform: translateZ(0);
  will-change: opacity;
}

.weather-toggle__thumb {
  position: absolute;
  z-index: 4;
  top: 2px;
  left: 2px;
  width: 16px;
  height: 16px;
  box-sizing: border-box;
  pointer-events: none;
  background: linear-gradient(145deg, #ffffff 0%, #f6f8fb 45%, #e6ebf3 100%);
  border: 1px solid rgba(255, 255, 255, 0.95);
  border-radius: 50%;
  box-shadow: 0 1px 3px rgba(19, 43, 74, 0.3), inset 0 1px 2px rgba(255, 255, 255, 0.95);
  backface-visibility: hidden;
  transform-origin: center;
  will-change: transform;
}

.weather-toggle__state {
  position: absolute;
  width: 1px;
  height: 1px;
  padding: 0;
  margin: -1px;
  overflow: hidden;
  white-space: nowrap;
  border: 0;
  clip: rect(0, 0, 0, 0);
}

@media (prefers-reduced-motion: reduce) {
  .weather-toggle {
    transition: none;

    &:active:not(.is-disabled) {
      transform: none;
    }
  }

  .weather-toggle__weather-layer,
  .weather-toggle__frame,
  .weather-toggle__thumb-cover,
  .weather-toggle__transition-light,
  .weather-toggle__thumb {
    will-change: auto;
  }
}
</style>
