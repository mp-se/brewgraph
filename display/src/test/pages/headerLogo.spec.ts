/*
 * Copyright (c) 2024-2026 Magnus Persson
 * SPDX-License-Identifier: GPL-3.0-only
 */

import { beforeEach, describe, expect, it, vi } from 'vitest';
import { flushPromises, mount } from '@vue/test-utils';
import axios from 'axios';

import BottleListView from '@/pages/BottleListView.vue';
import TapListView from '@/pages/TapListView.vue';

vi.mock('axios');
const mockedAxios = vi.mocked(axios);

function serveContext(logoUrl: string | null) {
  mockedAxios.get.mockImplementation((url: string) => Promise.resolve({
    data: url === '/d'
      ? { breweryName: 'Brewery', logoUrl, theme: 'dark', primaryColor: null }
      : [],
  }));
}

describe.each([
  ['TapListView', TapListView],
  ['BottleListView', BottleListView],
])('%s header logo', (_name, View) => {
  beforeEach(() => mockedAxios.get.mockReset());

  it('renders the logo as a labelled mask when logoUrl is set', async () => {
    serveContext('/logos/hop.svg');
    const wrapper = mount(View);
    await flushPromises();

    const logo = wrapper.find('.display-logo');
    expect(logo.exists()).toBe(true);
    expect(logo.attributes('role')).toBe('img');
    expect(logo.attributes('aria-label')).toBe('Venue logo');
    expect(logo.attributes('style')).toContain('--display-logo-url: url(/logos/hop.svg)');
    expect(wrapper.find('img').exists()).toBe(false);
  });

  it('renders no logo when logoUrl is null', async () => {
    serveContext(null);
    const wrapper = mount(View);
    await flushPromises();

    expect(wrapper.find('.display-logo').exists()).toBe(false);
  });
});
