import { businessFieldLabel } from '../ticket/catalog'

export function missingFieldOptions(field: string) {
  if (/couponType/i.test(field)) return ['满减券', '饭票优惠券', '影票优惠券']
  if (/reason/i.test(field)) return ['达标未发放', '券已过期未使用', '活动资格争议']
  if (/transactionAmount|amount/i.test(field)) return ['以交易流水为准', '客户待提供金额']
  if (/transactionDate|date/i.test(field)) return ['以账单日为准', '客户待提供日期']
  return ['客户来电补充', '接单单位补充', '坐席核实补充']
}

export function buildSupplementText(missingFields: string[], draft: Record<string, string>, includeEmpty = false) {
  const rows = missingFields
    .map(field => {
      const value = String(draft[field] || '').trim()
      if (!value && !includeEmpty) return ''
      return `${businessFieldLabel(field)}：${value || '待客户补充'}`
    })
    .filter(Boolean)
  return rows.length ? `客户补充信息：\n${rows.map(row => `- ${row}`).join('\n')}` : ''
}

export function buildSupplementQuestion(missingFields: string[]) {
  const labels = missingFields.map(businessFieldLabel).join('、')
  return labels
    ? `您好，为继续处理本工单，请补充${labels}。收到后我行将继续核验并反馈处理结果。`
    : '当前暂无必须追问客户的信息。'
}
