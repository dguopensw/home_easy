/// <reference types="webxr" />
/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_API_URL: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}

declare global {
  namespace JSX {
    interface IntrinsicElements {
      'model-viewer': React.DetailedHTMLProps<React.HTMLAttributes<HTMLElement>, HTMLElement> & {
        src?: string
        alt?: string
        ar?: boolean | string
        'ar-modes'?: string
        'camera-controls'?: boolean | string
        'auto-rotate'?: string | boolean
        'auto-rotate-delay'?: string
        'rotation-per-second'?: string
        'shadow-intensity'?: string
        exposure?: string
        'environment-image'?: string
      }
    }
  }
}