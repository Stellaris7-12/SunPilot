import { Motion } from 'ai-motion'

import { isPageDark } from './checkDarkMode'

import styles from './SimulatorMask.module.css'
import cursorStyles from './cursor.module.css'

export class SimulatorMask extends EventTarget {
	shown: boolean = false
	wrapper = document.createElement('div')
	motion: Motion | null = null

	#disposed = false

	#cursor = document.createElement('div')

	#currentCursorX = 0
	#currentCursorY = 0

	#targetCursorX = 0
	#targetCursorY = 0
	#syncBoundsListener = () => this.#syncBusinessBounds()

	constructor() {
		super()

		this.wrapper.id = 'page-agent-runtime_simulator-mask'
		this.wrapper.className = styles.wrapper
		this.wrapper.setAttribute('data-browser-use-ignore', 'true')
		this.wrapper.setAttribute('data-page-agent-ignore', 'true')

		try {
			const motion = new Motion({
				mode: isPageDark() ? 'dark' : 'light',
				styles: { position: 'absolute', inset: '0' },
			})
			this.motion = motion
			this.wrapper.appendChild(motion.element)
			motion.autoResize(this.wrapper)
		} catch (e) {
			console.warn('[SimulatorMask] Motion overlay unavailable:', e)
		}

		// Capture all mouse, keyboard, and wheel events
		this.wrapper.addEventListener('click', (e) => {
			e.stopPropagation()
			e.preventDefault()
		})
		this.wrapper.addEventListener('mousedown', (e) => {
			e.stopPropagation()
			e.preventDefault()
		})
		this.wrapper.addEventListener('mouseup', (e) => {
			e.stopPropagation()
			e.preventDefault()
		})
		this.wrapper.addEventListener('mousemove', (e) => {
			e.stopPropagation()
			e.preventDefault()
		})
		this.wrapper.addEventListener('wheel', (e) => {
			e.stopPropagation()
			e.preventDefault()
		})
		this.wrapper.addEventListener('keydown', (e) => {
			e.stopPropagation()
			e.preventDefault()
		})
		this.wrapper.addEventListener('keyup', (e) => {
			e.stopPropagation()
			e.preventDefault()
		})

		// Create AI cursor
		this.#createCursor()
		// this.show()

		document.body.appendChild(this.wrapper)
		this.#syncBusinessBounds()

		this.#moveCursorToTarget()

		// global events
		// @note Mask should be isolated from the rest of the code.
		// Global events are easier to manage and cleanup.

		const movePointerToListener = (event: Event) => {
			const { x, y } = (event as CustomEvent).detail
			this.setCursorPosition(x, y)
		}
		const clickPointerListener = () => {
			this.triggerClickAnimation()
		}
		const enablePassThroughListener = () => {
			this.wrapper.style.pointerEvents = 'none'
		}
		const disablePassThroughListener = () => {
			this.wrapper.style.pointerEvents = 'auto'
		}

		window.addEventListener('PageAgent::MovePointerTo', movePointerToListener)
		window.addEventListener('PageAgent::ClickPointer', clickPointerListener)
		window.addEventListener('PageAgent::EnablePassThrough', enablePassThroughListener)
		window.addEventListener('PageAgent::DisablePassThrough', disablePassThroughListener)
		window.addEventListener('resize', this.#syncBoundsListener)
		window.addEventListener('scroll', this.#syncBoundsListener, true)

		this.addEventListener('dispose', () => {
			window.removeEventListener('PageAgent::MovePointerTo', movePointerToListener)
			window.removeEventListener('PageAgent::ClickPointer', clickPointerListener)
			window.removeEventListener('PageAgent::EnablePassThrough', enablePassThroughListener)
			window.removeEventListener('PageAgent::DisablePassThrough', disablePassThroughListener)
			window.removeEventListener('resize', this.#syncBoundsListener)
			window.removeEventListener('scroll', this.#syncBoundsListener, true)
		})
	}

	#syncBusinessBounds() {
		const panel = document.querySelector('.copilot[data-sunpilot-panel]')
		if (!(panel instanceof HTMLElement)) {
			this.wrapper.style.right = '0px'
			return
		}

		const rect = panel.getBoundingClientRect()
		const isRightRail = rect.left > window.innerWidth * 0.45 && rect.top < window.innerHeight
		if (!isRightRail) {
			this.wrapper.style.right = '0px'
			return
		}

		const rightInset = Math.max(0, window.innerWidth - rect.left)
		this.wrapper.style.right = `${rightInset}px`
	}

	#createCursor() {
		this.#cursor.className = cursorStyles.cursor

		// Create ripple effect container
		const rippleContainer = document.createElement('div')
		rippleContainer.className = cursorStyles.cursorRipple
		this.#cursor.appendChild(rippleContainer)

		// Create filling layer
		const fillingLayer = document.createElement('div')
		fillingLayer.className = cursorStyles.cursorFilling
		this.#cursor.appendChild(fillingLayer)

		// Create border layer
		const borderLayer = document.createElement('div')
		borderLayer.className = cursorStyles.cursorBorder
		this.#cursor.appendChild(borderLayer)

		this.wrapper.appendChild(this.#cursor)
	}

	#moveCursorToTarget() {
		if (this.#disposed) return

		const newX = this.#currentCursorX + (this.#targetCursorX - this.#currentCursorX) * 0.2
		const newY = this.#currentCursorY + (this.#targetCursorY - this.#currentCursorY) * 0.2

		const xDistance = Math.abs(newX - this.#targetCursorX)
		if (xDistance > 0) {
			if (xDistance < 2) {
				this.#currentCursorX = this.#targetCursorX
			} else {
				this.#currentCursorX = newX
			}
			this.#cursor.style.left = `${this.#currentCursorX}px`
		}

		const yDistance = Math.abs(newY - this.#targetCursorY)
		if (yDistance > 0) {
			if (yDistance < 2) {
				this.#currentCursorY = this.#targetCursorY
			} else {
				this.#currentCursorY = newY
			}
			this.#cursor.style.top = `${this.#currentCursorY}px`
		}

		requestAnimationFrame(() => this.#moveCursorToTarget())
	}

	setCursorPosition(x: number, y: number) {
		if (this.#disposed) return

		this.#targetCursorX = x
		this.#targetCursorY = y
	}

	triggerClickAnimation() {
		if (this.#disposed) return

		this.#cursor.classList.remove(cursorStyles.clicking)
		// Force reflow to restart animation
		void this.#cursor.offsetHeight
		this.#cursor.classList.add(cursorStyles.clicking)
	}

	show() {
		if (this.shown || this.#disposed) return

		this.shown = true
		this.#syncBusinessBounds()
		this.motion?.start()
		this.motion?.fadeIn()

		this.wrapper.classList.add(styles.visible)

		// Initialize cursor position
		this.#currentCursorX = window.innerWidth / 2
		this.#currentCursorY = window.innerHeight / 2
		this.#targetCursorX = this.#currentCursorX
		this.#targetCursorY = this.#currentCursorY
		this.#cursor.style.left = `${this.#currentCursorX}px`
		this.#cursor.style.top = `${this.#currentCursorY}px`
	}

	hide() {
		if (!this.shown || this.#disposed) return

		this.shown = false
		this.motion?.fadeOut()
		this.motion?.pause()

		this.#cursor.classList.remove(cursorStyles.clicking)

		setTimeout(() => {
			this.wrapper.classList.remove(styles.visible)
		}, 800) // Match the animation duration
	}

	dispose() {
		this.#disposed = true
		this.motion?.dispose()
		this.wrapper.remove()
		this.dispatchEvent(new Event('dispose'))
	}
}
