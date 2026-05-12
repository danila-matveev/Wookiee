import '@testing-library/jest-dom'

// jsdom does not implement ResizeObserver — polyfill for cmdk and other libs that use it
if (typeof ResizeObserver === 'undefined') {
  globalThis.ResizeObserver = class ResizeObserver {
    observe() {}
    unobserve() {}
    disconnect() {}
  }
}

// jsdom does not implement scrollIntoView — polyfill for cmdk item highlight
if (typeof Element !== 'undefined' && !Element.prototype.scrollIntoView) {
  Element.prototype.scrollIntoView = () => {}
}
