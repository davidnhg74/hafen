/**
 * Tests for the public /troubleshoot page.
 *
 * The page is the entry point a stuck DBA hits at 2am — anonymous,
 * no signup. We test the UX surface (paste → submit → render) and
 * the contract with the API helper (mocked) without going to the
 * real network.
 */
import { afterEach, describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';

import * as api from '@/app/lib/api';

import TroubleshootPage from './page';


const FAKE_DIAGNOSIS: api.Diagnosis = {
  likely_cause: 'Wrong listener SID',
  recommended_action: '1. Verify listener.ora exposes the right SID.',
  code_suggestion: 'lsnrctl status',
  confidence: 'high',
  escalate_if: 'the listener is up but errors persist',
  analyzed_bytes: 1024,
  extracted_line_count: 12,
  used_ai: true,
  analysis_id: 'fake-id-001',
  usage_remaining: 7,
};


describe('TroubleshootPage', () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('renders the headline and tabs', () => {
    render(<TroubleshootPage />);
    expect(screen.getByText(/Stuck on an Oracle migration/i)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Paste' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Upload files' })).toBeInTheDocument();
  });

  it('shows the trim cheat sheet on demand', () => {
    render(<TroubleshootPage />);
    fireEvent.click(screen.getByRole('button', { name: /show how to trim/i }));
    expect(screen.getByText(/grep -B 5/)).toBeInTheDocument();
  });

  it('paste → submit → renders diagnosis with footer', async () => {
    const spy = vi.spyOn(api, 'analyzeLogsPaste').mockResolvedValue(FAKE_DIAGNOSIS);
    render(<TroubleshootPage />);

    const textarea = screen.getByRole('textbox');
    fireEvent.change(textarea, { target: { value: 'ORA-01017: bad creds' } });
    fireEvent.click(screen.getByRole('button', { name: 'Diagnose' }));

    await waitFor(() => {
      expect(spy).toHaveBeenCalledWith({
        logs: 'ORA-01017: bad creds',
        context: undefined,
        stage: undefined,
      });
      expect(screen.getByText('Wrong listener SID')).toBeInTheDocument();
    });

    // "What we analyzed" footer.
    expect(screen.getByText(/Analyzed 1\.0 KB/i)).toBeInTheDocument();
    expect(screen.getByText(/extracted 12 relevant lines/i)).toBeInTheDocument();
    expect(screen.getByText(/7 of your daily analyses remaining/i)).toBeInTheDocument();
  });

  it('submit button disabled until input is non-empty', () => {
    render(<TroubleshootPage />);
    const submit = screen.getByRole('button', { name: 'Diagnose' });
    expect(submit).toBeDisabled();

    const textarea = screen.getByRole('textbox');
    fireEvent.change(textarea, { target: { value: 'something' } });
    expect(submit).not.toBeDisabled();
  });

  it('"Try a sample" button populates the textarea', () => {
    render(<TroubleshootPage />);
    fireEvent.click(screen.getByRole('button', { name: /Try a sample/i }));
    const textarea = screen.getByRole('textbox') as HTMLTextAreaElement;
    expect(textarea.value).toContain('ORA-01017');
  });

  it('renders failure toast on API error', async () => {
    vi.spyOn(api, 'analyzeLogsPaste').mockRejectedValue({
      response: { data: { detail: 'pasted logs exceed your plan cap' } },
    });
    render(<TroubleshootPage />);
    fireEvent.change(screen.getByRole('textbox'), { target: { value: 'too big' } });
    fireEvent.click(screen.getByRole('button', { name: 'Diagnose' }));
    await waitFor(() => {
      expect(screen.getByText(/exceed your plan cap/i)).toBeInTheDocument();
    });
  });
});
