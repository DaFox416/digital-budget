import type { components } from './schema'

// Short names for the API schemas. Amounts are strings ("-387.56"): never parse them to floats.
type Schemas = components['schemas']

export type Account = Schemas['AccountRead']
export type Category = Schemas['CategoryRead']
export type Movement = Schemas['MovementRead']
export type Summary = Schemas['SummaryRead']
export type CardSummary = Schemas['CardSummaryRead']
export type Preferences = Schemas['PreferencesRead']
export type MovementCreate = Schemas['MovementCreate']
export type TransferCreate = Schemas['TransferCreate']
export type Commitment = Schemas['CommitmentRead']
export type InstallmentPlanCreate = Schemas['InstallmentPlanCreate']
export type MovementPreviewRequest = Schemas['MovementPreviewRequest']
export type MovementPreview = Schemas['MovementPreviewRead']
export type PurchaseWarning = Schemas['PurchaseWarningRead']
