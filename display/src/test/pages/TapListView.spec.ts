import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { flushPromises, mount } from '@vue/test-utils';
import axios from 'axios';

import TapListView from '@/pages/TapListView.vue';

vi.mock('axios');
const mockedAxios = vi.mocked(axios);

describe('TapListView', () => {
  beforeEach(() => {
    vi.useFakeTimers();
    mockedAxios.get.mockReset();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('loads context once and tokenless OSS taps at the shared contract paths', async () => {
    mockedAxios.get.mockImplementation((url: string) => Promise.resolve({
      data: url === '/d'
        ? { breweryName: 'Brewery', logoUrl: null, theme: 'dark', primaryColor: null }
        : [],
    }));
    mount(TapListView);
    await flushPromises();

    expect(mockedAxios.get).toHaveBeenCalledWith('/d');
    expect(mockedAxios.get).toHaveBeenCalledWith('/t');
  });

  it('uses token paths and renders the sanitized tap contract', async () => {
    mockedAxios.get.mockImplementation((url: string) => Promise.resolve({
      data: url === '/d/tenant-token'
        ? { breweryName: 'Brewery', logoUrl: null, theme: 'chalkboard', primaryColor: '#f59e0b' }
        : [{
          tapName: 'Tap 4', beerName: 'Hazy IPA', style: 'New England IPA',
          abv: 6.2, ibu: 45, ebc: 12,
          serving: {
            servingSince: '2026-09-13T10:30:00Z', totalVolume: 20,
            volumeRemaining: 12.4, volumePoured: 7.6, temperature: 5.2,
            temperatureAt: '2026-09-13T11:59:00Z', pressure: 110.4,
            pressureAt: '2026-09-13T11:59:00Z',
            lastPour: { at: '2026-09-13T11:59:00Z', amount: 0.4, volumeRemaining: 12.4 },
          },
        }],
    }));
    const wrapper = mount(TapListView, { props: { token: 'tenant-token' } });
    await flushPromises();

    expect(mockedAxios.get).toHaveBeenCalledWith('/d/tenant-token');
    expect(mockedAxios.get).toHaveBeenCalledWith('/t/tenant-token');
    expect(wrapper.text()).toContain('Tap 4');
    expect(wrapper.text()).toContain('Hazy IPA');
    expect(wrapper.text()).toContain('12.4 / 20.0 L');
    expect(wrapper.text()).not.toContain('servingVesselId');
  });

  const calls = (url: string) => mockedAxios.get.mock.calls.filter(([u]) => u === url).length;

  it('polls taps every minute and the display context every five', async () => {
    mockedAxios.get.mockResolvedValue({ data: [] });
    const wrapper = mount(TapListView);
    await flushPromises();
    vi.advanceTimersByTime(60_000);
    await flushPromises();

    expect(calls('/d')).toBe(1);
    expect(calls('/t')).toBe(2);

    vi.advanceTimersByTime(4 * 60_000);
    await flushPromises();
    wrapper.unmount();

    expect(calls('/d')).toBe(2);
    expect(calls('/t')).toBe(6);
  });

  it('picks up a settings change on a display that is never reloaded', async () => {
    let brewery = 'Old Name';
    mockedAxios.get.mockImplementation((url: string) => Promise.resolve({
      data: url === '/d'
        ? { breweryName: brewery, logoUrl: null, theme: 'dark', primaryColor: null }
        : [],
    }));
    const wrapper = mount(TapListView);
    await flushPromises();
    expect(wrapper.find('h1').text()).toBe('Old Name');

    brewery = 'New Name';
    vi.advanceTimersByTime(5 * 60_000);
    await flushPromises();
    expect(wrapper.find('h1').text()).toBe('New Name');
    wrapper.unmount();
  });

  it('keeps the current settings when a context refresh fails', async () => {
    let contextDown = false;
    mockedAxios.get.mockImplementation((url: string) => {
      if (url === '/d' && contextDown) return Promise.reject(new Error('offline'));
      return Promise.resolve({
        data: url === '/d'
          ? { breweryName: 'Brewery', logoUrl: null, theme: 'dark', primaryColor: null }
          : [],
      });
    });
    const wrapper = mount(TapListView);
    await flushPromises();

    contextDown = true;
    vi.advanceTimersByTime(5 * 60_000);
    await flushPromises();

    expect(wrapper.find('h1').text()).toBe('Brewery');
    expect(wrapper.text()).not.toContain('unavailable');
    wrapper.unmount();
  });

  it('still shows taps, under default settings, when the context never loads', async () => {
    mockedAxios.get.mockImplementation((url: string) => (url === '/d'
      ? Promise.reject(new Error('offline'))
      : Promise.resolve({ data: [{ tapName: 'Tap 1', beerName: null, serving: null }] })));
    const wrapper = mount(TapListView);
    await flushPromises();

    expect(wrapper.find('h1').text()).toBe('Tap List');
    expect(wrapper.text()).toContain('Tap 1');
    expect(wrapper.text()).not.toContain('unavailable');
    wrapper.unmount();
  });

  it('shows an error when the display itself cannot be loaded', async () => {
    mockedAxios.get.mockRejectedValue(new Error('404'));
    const wrapper = mount(TapListView, { props: { token: 'unknown' } });
    await flushPromises();

    expect(wrapper.text()).toContain('Display not found or unavailable.');
    wrapper.unmount();
  });

  it('moves the header date forward on a display left running overnight', async () => {
    vi.setSystemTime(new Date('2026-09-27T23:59:30'));
    mockedAxios.get.mockResolvedValue({ data: [] });
    const wrapper = mount(TapListView);
    await flushPromises();
    const before = wrapper.find('.display-header p').text();

    vi.advanceTimersByTime(60_000);
    await flushPromises();
    const after = wrapper.find('.display-header p').text();
    wrapper.unmount();

    expect(before).toContain(new Date('2026-09-27T12:00:00').toLocaleDateString());
    expect(after).toContain(new Date('2026-09-28T12:00:00').toLocaleDateString());
  });
});
