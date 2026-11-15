// Shared by the capture and edit panels, so both look and behave the same

// text-base on phones: fields inherit the label's 14 px, and iOS zooms in on fields under 16 px
export const fieldBase =
  'mt-1 block w-full rounded-lg border-0 bg-white px-3 py-2 text-slate-900 ring-1 ring-slate-300 focus:ring-2 focus:ring-sky-500'
export const fieldClass = `${fieldBase} text-base sm:text-sm`
export const labelClass = 'block text-sm font-medium text-slate-700'
