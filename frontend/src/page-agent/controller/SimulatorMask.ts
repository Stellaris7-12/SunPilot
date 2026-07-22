const styleId = 'ticket-page-agent-mask-style';

function ensureStyles() {
  if (document.getElementById(styleId)) return;
  const style = document.createElement('style');
  style.id = styleId;
  style.textContent = `
    .page-agent-cursor {
      position: fixed;
      z-index: 10000;
      width: 18px;
      height: 18px;
      border: 2px solid #0f766e;
      border-radius: 999px;
      background: rgba(20, 184, 166, 0.16);
      box-shadow: 0 0 0 8px rgba(20, 184, 166, 0.08);
      pointer-events: none;
      transform: translate(-50%, -50%);
      transition: left 360ms ease, top 360ms ease, transform 140ms ease;
    }
    .page-agent-cursor.clicking {
      transform: translate(-50%, -50%) scale(0.74);
      box-shadow: 0 0 0 16px rgba(20, 184, 166, 0.16);
    }
    .page-agent-highlight {
      position: fixed;
      z-index: 9999;
      border: 2px solid #f59e0b;
      background: rgba(245, 158, 11, 0.08);
      box-shadow: 0 0 0 9999px rgba(15, 23, 42, 0.04);
      pointer-events: none;
      transition: left 220ms ease, top 220ms ease, width 220ms ease, height 220ms ease, opacity 180ms ease;
    }
  `;
  document.head.appendChild(style);
}

function centerOf(element: Element) {
  const rect = element.getBoundingClientRect();
  return {
    x: rect.left + rect.width / 2,
    y: rect.top + Math.min(rect.height / 2, 38),
    rect,
  };
}

export class SimulatorMask {
  private cursor: HTMLDivElement | null = null;
  private highlightBox: HTMLDivElement | null = null;

  constructor() {
    if (typeof document !== 'undefined') ensureStyles();
  }

  mount() {
    if (!this.cursor) {
      this.cursor = document.createElement('div');
      this.cursor.className = 'page-agent-cursor';
      this.cursor.style.left = '50%';
      this.cursor.style.top = '50%';
      document.body.appendChild(this.cursor);
    }
    if (!this.highlightBox) {
      this.highlightBox = document.createElement('div');
      this.highlightBox.className = 'page-agent-highlight';
      this.highlightBox.style.opacity = '0';
      document.body.appendChild(this.highlightBox);
    }
  }

  async moveTo(element: Element) {
    this.mount();
    const { x, y } = centerOf(element);
    if (this.cursor) {
      this.cursor.style.left = `${x}px`;
      this.cursor.style.top = `${y}px`;
    }
    await this.pause(380);
  }

  async highlight(element: Element) {
    this.mount();
    const rect = element.getBoundingClientRect();
    if (this.highlightBox) {
      this.highlightBox.style.left = `${Math.max(rect.left - 4, 4)}px`;
      this.highlightBox.style.top = `${Math.max(rect.top - 4, 4)}px`;
      this.highlightBox.style.width = `${rect.width + 8}px`;
      this.highlightBox.style.height = `${rect.height + 8}px`;
      this.highlightBox.style.opacity = '1';
    }
    await this.pause(260);
  }

  async click() {
    this.mount();
    this.cursor?.classList.add('clicking');
    await this.pause(140);
    this.cursor?.classList.remove('clicking');
  }

  hideHighlight() {
    if (this.highlightBox) this.highlightBox.style.opacity = '0';
  }

  dispose() {
    this.cursor?.remove();
    this.highlightBox?.remove();
    this.cursor = null;
    this.highlightBox = null;
  }

  pause(ms: number) {
    return new Promise<void>(resolve => window.setTimeout(resolve, ms));
  }
}
