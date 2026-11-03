import { setupServer } from 'msw/node'
import { demoHandlers } from './demo'

export const server = setupServer(...demoHandlers)
