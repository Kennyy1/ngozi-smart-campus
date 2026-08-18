import '@testing-library/jest-dom/vitest';
import {afterEach} from 'vitest';
import {cleanup} from '@testing-library/react';
import {vi} from 'vitest';

vi.stubEnv('VITE_API_BASE_URL','http://web-test-api.invalid/api/v1');

afterEach(()=>{cleanup();sessionStorage.clear();vi.restoreAllMocks()});
