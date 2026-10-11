import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'

import QueryResultTable from './QueryResultTable.vue'

describe('query results', () => {
  it('paginates, sorts decimal values and marks truncation', async () => {
    const wrapper = mount(QueryResultTable, {
      props: {
        result: {
          columns: [{ name: 'amount', data_type: 'numeric' }],
          rows: Array.from({ length: 55 }, (_, i) => [(55 - i).toFixed(2)]),
          row_count: 55,
          truncated: true,
          elapsed_ms: 10,
        },
      },
    })
    expect(wrapper.findAll('tbody tr')).toHaveLength(50)
    expect(wrapper.text()).toContain('结果已截断')
    await wrapper.get('th button').trigger('click')
    expect(wrapper.get('tbody td').text()).toBe('1.00')
    await wrapper.findAll('.pagination button')[1]!.trigger('click')
    expect(wrapper.findAll('tbody tr')).toHaveLength(5)
    expect(wrapper.get('tbody td').text()).toBe('51.00')
  })

  it('shows empty results as success and renders SQL-looking cells as text', () => {
    const result = {
      columns: [{ name: 'value', data_type: 'text' }],
      rows: [],
      row_count: 0,
      truncated: false,
      elapsed_ms: 1,
    }
    const empty = mount(QueryResultTable, { props: { result } })
    expect(empty.text()).toContain('查询成功，当前条件下没有数据')
    const populated = mount(QueryResultTable, {
      props: { result: { ...result, rows: [['<script>alert(1)</script>']], row_count: 1 } },
    })
    expect(populated.find('script').exists()).toBe(false)
    expect(populated.get('td').text()).toBe('<script>alert(1)</script>')
  })
})
