import { describe, expect, it } from 'vitest'

import { isFieldVisible, validateServiceAnswers, type ServiceAnswers } from '@/domain/serviceIntake'

import { catalogForms } from './fixtures/catalog.generated'

/**
 * 題組定義本身由後端提供（見 tests/fixtures/catalog.generated.ts，自後端產生）。
 * 這裡驗的是前端的「即時回饋」驗證器——後端在收單時會再驗一次。
 */
describe('service intake validation', () => {
  it('receives an actionable data-driven form for every catalog service', () => {
    expect(Object.keys(catalogForms)).toHaveLength(9)
    for (const form of Object.values(catalogForms)) {
      expect(form.fields.length).toBeGreaterThan(0)
      expect(['inquiry', 'order', 'reservation', 'shipment']).toContain(form.action)
      expect(form.dataUse.length).toBeGreaterThan(0)
    }
  })

  it('can complete every visible service form with valid deterministic fixture answers', () => {
    for (const form of Object.values(catalogForms)) {
      const answers: ServiceAnswers = {}
      for (const field of form.fields) {
        if (!isFieldVisible(field, answers)) continue
        if (field.type === 3) answers[field.id] = field.options?.[0]?.value ?? ''
        else if (field.type === 1 && field.numberOnly) answers[field.id] = field.min ?? 1
        else if (field.type === 9) answers[field.id] = field.minDate ?? '2026-07-27'
        else if (field.type === 5) answers[field.id] = { county_name: '臺北市', district_name: '大同區' }
        else if (field.type === 8) answers[field.id] = { name: '王小明', mobile: '0912345678', address: '臺北市大同區民生西路 1 號' }
        else if (field.type === 10) answers[field.id] = { name: '王小明', mobile: '0912345678' }
        else answers[field.id] = '展示用需求說明'
      }
      expect(validateServiceAnswers(form, answers), form.serviceId).toEqual({})
    }
  })

  it('validates visible required fields and conditional fields', () => {
    const form = catalogForms['service-repair']!

    expect(validateServiceAnswers(form, {})).toMatchObject({ repairType: expect.any(String), urgency: expect.any(String), region: expect.any(String), contact: expect.any(String) })
    const required = {
      urgency: 'normal',
      region: { county_name: '臺北市', district_name: '大同區' },
      date: form.fields.find((field) => field.id === 'date')!.minDate!,
      slot: 'morning',
      contact: { name: '王小明', mobile: '0912345678', address: '臺北市大同區民生西路 1 號' },
    }
    expect(validateServiceAnswers(form, { repairType: 'plumbing', ...required })).toEqual({})
    expect(validateServiceAnswers(form, { repairType: 'other', ...required })).toMatchObject({ detail: expect.any(String) })
  })

  it('rejects unknown options, whitespace-only text, and dates outside the booking window', () => {
    const repair = catalogForms['service-repair']!
    const aircon = catalogForms['service-aircon']!

    expect(validateServiceAnswers(repair, { repairType: 'unknown', urgency: 'normal' })).toMatchObject({ repairType: expect.any(String) })
    expect(validateServiceAnswers(repair, { repairType: 'other', detail: '   ', urgency: 'normal' })).toMatchObject({ detail: expect.any(String) })
    expect(validateServiceAnswers(aircon, { airconType: 'split', quantity: 1, date: '2026-09-01', slot: 'morning' })).toMatchObject({ date: expect.any(String) })
  })

  it('carries the booking window sent by the backend', () => {
    const aircon = catalogForms['service-aircon']!
    const dateField = aircon.fields.find((field) => field.id === 'date')
    expect(dateField).toMatchObject({ type: 9, minDate: '2026-07-26', maxDate: '2026-08-08' })
  })
})
