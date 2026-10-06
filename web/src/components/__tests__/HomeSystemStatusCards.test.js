import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import HomeSystemStatusCards from '../HomeSystemStatusCards.vue'

function mountStatusCards(schedulerStatus = null, deviceProps = {}) {
  return mount(HomeSystemStatusCards, {
    props: {
      schedulerStatus,
      ...deviceProps,
      deviceCount: 1,
      batchCount: 2,
      vesselCount: 3,
      tapCount: 4,
      gravityCount: 5,
      pourCount: 6,
      pressureCount: 7
    },
    global: {
      components: {
        AppCard: {
          props: ['header'],
          template: '<section><h2>{{ header }}</h2><slot /></section>'
        }
      }
    }
  })
}

describe('HomeSystemStatusCards', () => {
  it('renders database metrics and scheduler task names', () => {
    const wrapper = mountStatusCards([
      { name: 'task_check_database', nextRunIn: 300 },
      { name: 'task_drain_gravity_forward_queue', nextRunIn: 45 },
      { name: 'unknown_task', nextRunIn: 3600 }
    ])

    expect(wrapper.text()).toContain('Database maintenance: 5 m')
    expect(wrapper.text()).toContain('Forward gravity data: 45 s')
    expect(wrapper.text()).toContain('Unknown mapping: 1 h')
    expect(wrapper.text()).toContain('5 gravity points in database')
    expect(wrapper.text()).toContain('6 pour points in database')
  })

  it('renders the disabled scheduler state', () => {
    expect(mountStatusCards([]).text()).toContain('Scheduler disabled')
  })

  it('renders chamber and Kegmon status cards, including device errors', () => {
    const wrapper = mountStatusCards(null, {
      chamberTemps: [
        { mdns: 'chamber-one', pid_fridge_temp_connected: true, pid_fridge_temp: 4, pid_temp_format: 'C' },
        { mdns: 'chamber-two', error: 'Unavailable' }
      ],
      kegmonTaps: [
        { mdns: 'kegmon-one', beer_volume1: 500, glass1: 2, beer_volume2: 750, glass2: 3, temperature: 5, temp_format: 'C' }
      ]
    })

    expect(wrapper.text()).toContain('Chamber: chamber-one')
    expect(wrapper.text()).toContain('Fridge temp: 4 °C')
    expect(wrapper.text()).toContain('Unavailable')
    expect(wrapper.text()).toContain('Tap1: 5.0 L, (2 glasses)')
    expect(wrapper.text()).toContain('Tap2: 7.5 L, (3 glasses)')
  })
})
