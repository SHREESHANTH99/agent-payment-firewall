import { setupWorker } from 'msw/browser'
import { demoHandlers } from './demo'

export const worker = setupWorker(...demoHandlers)
