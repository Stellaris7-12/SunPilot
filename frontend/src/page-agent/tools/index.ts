/**
 * Internal tools for PageAgent.
 * @note Adapted from browser-use
 */
import * as z from 'zod/v4'

import type { PageAgentCore } from '../core/PageAgentCore'
import { waitFor } from '../core/utils'
import { clickElement, inputTextElement, selectOptionElement } from '../controller/actions'

/**
 * Per-invocation context passed to every tool execution.
 * Tools MUST honor `signal` to support cooperative cancellation.
 */
export interface ToolContext {
	signal: AbortSignal
}

/**
 * Internal tool definition that has access to PageAgent `this` context
 */
export interface PageAgentTool<TParams = any> {
	// name: string
	description: string
	inputSchema: z.ZodType<TParams>
	execute: (this: PageAgentCore, args: TParams, ctx: ToolContext) => Promise<string>
}

export function tool<TParams>(options: PageAgentTool<TParams>): PageAgentTool<TParams> {
	return options
}

/**
 * Internal tools for PageAgent.
 * Note: Using any to allow different parameter types for each tool
 */
export const tools = new Map<string, PageAgentTool>()

function cssString(value: string) {
	return value.replace(/\\/g, '\\\\').replace(/"/g, '\\"')
}

function findSemanticTarget(target: string): HTMLElement {
	const byId = document.getElementById(target)
	if (byId instanceof HTMLElement) return byId
	const selector = `[data-page-agent-target="${cssString(target)}"]`
	const element = document.querySelector(selector)
	if (element instanceof HTMLElement) return element
	throw new Error(`Semantic target not found: ${target}`)
}

async function fillElement(element: HTMLElement, value: string) {
	if (element instanceof HTMLSelectElement) {
		const option = Array.from(element.options).find(item =>
			item.value === value || item.textContent?.trim() === value.trim()
		)
		if (option) {
			element.value = option.value
			element.dispatchEvent(new Event('change', { bubbles: true }))
			await waitFor(0.1)
			return
		}
		await selectOptionElement(element, value)
		return
	}
	await inputTextElement(element, value)
}

function brieflyMark(element: HTMLElement) {
	const previousOutline = element.style.outline
	const previousOffset = element.style.outlineOffset
	element.style.outline = '2px solid #0f766e'
	element.style.outlineOffset = '2px'
	window.setTimeout(() => {
		element.style.outline = previousOutline
		element.style.outlineOffset = previousOffset
	}, 1400)
}

tools.set(
	'done',
	tool({
		description:
			'Complete task. Text is your final response to the user — keep it concise unless the user explicitly asks for detail.',
		inputSchema: z.object({
			text: z.string(),
			success: z.boolean().default(true),
		}),
		execute: async function () {
			// @note main loop will handle this one
			return Promise.resolve('Task completed')
		},
	})
)

tools.set(
	'wait',
	tool({
		description: 'Wait for x seconds. Can be used to wait until the page or data is fully loaded.',
		inputSchema: z.object({
			seconds: z.number().min(1).max(10).default(1),
		}),
		execute: async function (this: PageAgentCore, input, { signal }) {
			// try to subtract LLM calling time from the actual wait time
			const lastTimeUpdate = await this.pageController.getLastUpdateTime()
			const secondsSinceLastUpdate = (Date.now() - lastTimeUpdate) / 1000
			const actualWaitTime = Math.max(0, input.seconds - secondsSinceLastUpdate)
			console.log(`actualWaitTime: ${actualWaitTime} seconds`)
			await waitFor(actualWaitTime, signal)

			const waitedSeconds = (secondsSinceLastUpdate + actualWaitTime).toFixed(2)
			return `✅ Waited for ${waitedSeconds} seconds.`
		},
	})
)

tools.set(
	'ask_user',
	tool({
		description:
			'Ask the user a question and wait for their answer. Use this if you need more information or clarification.',
		inputSchema: z.object({
			question: z.string(),
		}),
		execute: async function (this: PageAgentCore, input, { signal }) {
			if (!this.onAskUser) {
				throw new Error('ask_user tool requires onAskUser callback to be set')
			}
			const answer = await this.onAskUser(input.question, { signal })
			return `User answered: ${answer}`
		},
	})
)

tools.set(
	'click_element_by_index',
	tool({
		description: 'Click element by index',
		inputSchema: z.object({
			index: z.int().min(0),
		}),
		execute: async function (this: PageAgentCore, input) {
			const result = await this.pageController.clickElement(input.index)
			return result.message
		},
	})
)

tools.set(
	'input_text',
	tool({
		description: 'Click and type text into an interactive input element',
		inputSchema: z.object({
			index: z.int().min(0),
			text: z.string(),
		}),
		execute: async function (this: PageAgentCore, input) {
			const result = await this.pageController.inputText(input.index, input.text)
			return result.message
		},
	})
)

tools.set(
	'select_dropdown_option',
	tool({
		description:
			'Select dropdown option for interactive element index by the text of the option you want to select',
		inputSchema: z.object({
			index: z.int().min(0),
			text: z.string(),
		}),
		execute: async function (this: PageAgentCore, input) {
			const result = await this.pageController.selectOption(input.index, input.text)
			return result.message
		},
	})
)

/**
 * @note Reference from browser-use
 */
tools.set(
	'scroll',
	tool({
		description:
			'Scroll vertically. Without index: scrolls the document. With index: scrolls the container at that index (or its nearest scrollable ancestor). Use index of a data-scrollable element to scroll a specific area.',
		inputSchema: z.object({
			down: z.boolean().default(true),
			num_pages: z.number().min(0).max(10).optional().default(0.1),
			pixels: z.number().int().min(0).optional(),
			index: z.number().int().min(0).optional(),
		}),
		execute: async function (this: PageAgentCore, input) {
			const result = await this.pageController.scroll({
				...input,
				numPages: input.num_pages,
			})
			return result.message
		},
	})
)

/**
 * @todo Tables need a dedicated parser to extract structured data. This tool is useless.
 */
tools.set(
	'scroll_horizontally',
	tool({
		description:
			'Scroll horizontally. Without index: scrolls the document. With index: scrolls the container at that index (or its nearest scrollable ancestor). Use index of a data-scrollable element to scroll a specific area.',
		inputSchema: z.object({
			right: z.boolean().default(true),
			pixels: z.number().int().min(0),
			index: z.number().int().min(0).optional(),
		}),
		execute: async function (this: PageAgentCore, input) {
			const result = await this.pageController.scrollHorizontally(input)
			return result.message
		},
	})
)

tools.set(
	'fill_form_by_targets',
	tool({
		description:
			'Fill multiple form fields by stable semantic targets such as data-page-agent-target or element id. Prefer this over DOM indexes when PageTask provides field targets.',
		inputSchema: z.object({
			fields: z.array(z.object({
				target: z.string().min(1),
				value: z.string(),
				label: z.string().optional(),
			})),
		}),
		execute: async function (this: PageAgentCore, input) {
			const results: string[] = []
			for (const field of input.fields) {
				const element = findSemanticTarget(field.target)
				await fillElement(element, field.value)
				results.push(`${field.label || field.target}=已填入`)
			}
			return `✅ Filled ${results.length} semantic field(s): ${results.join('；')}`
		},
	})
)

tools.set(
	'fill_textarea_by_target',
	tool({
		description:
			'Fill a textarea, input, or editable area by stable semantic target. Use for customer reply drafts and large text fields.',
		inputSchema: z.object({
			target: z.string().min(1),
			text: z.string(),
		}),
		execute: async function (this: PageAgentCore, input) {
			const element = findSemanticTarget(input.target)
			await fillElement(element, input.text)
			return `✅ Filled text into semantic target ${input.target}.`
		},
	})
)

tools.set(
	'select_option_by_label',
	tool({
		description: 'Select an option in a dropdown by stable semantic target and visible label or value.',
		inputSchema: z.object({
			target: z.string().min(1),
			value: z.string(),
		}),
		execute: async function (this: PageAgentCore, input) {
			const element = findSemanticTarget(input.target)
			if (!(element instanceof HTMLSelectElement)) {
				throw new Error(`Semantic target is not a select: ${input.target}`)
			}
			await fillElement(element, input.value)
			return `✅ Selected ${input.value} in ${input.target}.`
		},
	})
)

tools.set(
	'click_semantic_target',
	tool({
		description:
			'Click a stable semantic target by data-page-agent-target or id. Prefer this over click_element_by_index for TicketAgent pages.',
		inputSchema: z.object({
			target: z.string().min(1),
		}),
		execute: async function (this: PageAgentCore, input) {
			const element = findSemanticTarget(input.target)
			await clickElement(element)
			return `✅ Clicked semantic target ${input.target}.`
		},
	})
)

tools.set(
	'scroll_to_region',
	tool({
		description: 'Scroll to a stable page region by data-page-agent-target or id.',
		inputSchema: z.object({
			target: z.string().min(1),
		}),
		execute: async function (this: PageAgentCore, input) {
			const element = findSemanticTarget(input.target)
			element.scrollIntoView({ behavior: 'smooth', block: 'start' })
			brieflyMark(element)
			await waitFor(0.4)
			return `✅ Scrolled to region ${input.target}.`
		},
	})
)

tools.set(
	'locate_evidence',
	tool({
		description:
			'Locate and highlight evidence ids on the current TicketAgent page. If a specific evidence text is visible, scroll to it; otherwise scroll to the evidence region.',
		inputSchema: z.object({
			evidence_ids: z.array(z.string()).default([]),
			target: z.string().default('sunpilot-evidence'),
		}),
		execute: async function (this: PageAgentCore, input) {
			const candidates = Array.from(document.querySelectorAll('button, div, span, td, small, strong, textarea'))
			for (const evidenceId of input.evidence_ids) {
				const match = candidates.find(element => element.textContent?.includes(evidenceId))
				if (match instanceof HTMLElement) {
					match.scrollIntoView({ behavior: 'smooth', block: 'center' })
					brieflyMark(match)
					await waitFor(0.3)
					return `✅ Located evidence ${evidenceId}.`
				}
			}
			const region = findSemanticTarget(input.target)
			region.scrollIntoView({ behavior: 'smooth', block: 'start' })
			brieflyMark(region)
			await waitFor(0.3)
			return `✅ Evidence ids not directly visible; moved to ${input.target}.`
		},
	})
)

tools.set(
	'stop_for_human',
	tool({
		description: 'Stop automation and report that the task is waiting for human handling.',
		inputSchema: z.object({
			reason: z.string().default('需要人工处理'),
		}),
		execute: async function (this: PageAgentCore, input) {
			return `需要人工处理：${input.reason}`
		},
	})
)

tools.set(
	'wait_for_business_state',
	tool({
		description:
			'Wait until a stable semantic target or the document contains expected business state text. Use after submitting, processing, or navigating TicketAgent workflow states.',
		inputSchema: z.object({
			state: z.string().min(1),
			target: z.string().optional(),
			timeout_seconds: z.number().min(1).max(15).default(6),
		}),
		execute: async function (this: PageAgentCore, input, { signal }) {
			const deadline = Date.now() + input.timeout_seconds * 1000
			while (Date.now() < deadline) {
				if (signal.aborted) throw new DOMException('Aborted', 'AbortError')
				const container = input.target ? findSemanticTarget(input.target) : document.body
				if (container.textContent?.includes(input.state)) {
					if (container instanceof HTMLElement) brieflyMark(container)
					return `✅ Business state appeared: ${input.state}.`
				}
				await waitFor(0.3, signal)
			}
			throw new Error(`Business state did not appear within ${input.timeout_seconds}s: ${input.state}`)
		},
	})
)

tools.set(
	'execute_javascript',
	tool({
		description:
			'Execute JavaScript code on the current page. Supports async/await syntax. Use with caution! ' +
			'An `AbortSignal` named `signal` is available in scope: long-running async code MUST honor it ' +
			'(e.g. `await fetch(url, { signal })`, or `signal.throwIfAborted()` in loops)',
		inputSchema: z.object({
			script: z.string(),
		}),
		execute: async function (this: PageAgentCore, input, { signal }) {
			const result = await this.pageController.executeJavascript(input.script, signal)
			signal.throwIfAborted()
			return result.message
		},
	})
)

// @todo send_keys
// @todo upload_file
// @todo extract_structured_data
