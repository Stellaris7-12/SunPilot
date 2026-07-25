export interface BusinessCategory {
  id: string
  code: string
  label: string
  scenes: string[]
  pattern: RegExp
}

export const businessCategories: BusinessCategory[] = [
  { id: 'repayment', code: '11/71', label: '协商还款', scenes: ['协商还款'], pattern: /协商还款|还款方案|延期还款|11|71/i },
  { id: 'fraud-prevent', code: '12', label: '伪冒预防', scenes: ['伪冒预防'], pattern: /伪冒预防|非本人申请|投诉引导|12/i },
  { id: 'fraud-invest', code: '13', label: '伪冒调查', scenes: ['伪冒调查'], pattern: /伪冒调查|管制|BLOCK|X-DK|13/i },
  { id: 'customer-mgmt', code: '29', label: '客户经营', scenes: ['客户经营'], pattern: /客户经营|汽车分期|资料借阅|29/i },
  { id: 'marketing', code: '30', label: '市场企划', scenes: ['市场企划'], pattern: /市场企划|饭票|影票|掌上生活|优惠券|30/i },
  { id: 'chargeback', code: '41', label: '调单扣款', scenes: ['调单扣款'], pattern: /调单扣款|调单|扣款|公司资料异动|41/i },
  { id: 'credit', code: '42', label: '征信', scenes: ['征信'], pattern: /征信|贷后|逾期|E CODE|42/i },
]

export const businessFieldLabels: Record<string, string> = {
  couponType: '券种',
  reason: '补发原因',
  customerId: '客户号',
  customerName: '客户姓名',
  phone: '手机号',
  cardLast4: '卡号后四位',
  cardName: '卡片名称',
  activityName: '活动名称',
  transactionDate: '交易日期',
  transactionAmount: '交易金额',
  merchantName: '商户名称',
  applicationNo: '申请编号',
  accountStatus: '账户状态',
  creditReportType: '征信类型',
}

export function businessFieldLabel(field: string) {
  return businessFieldLabels[field] || field
}

export function businessText(value: string) {
  return Object.entries(businessFieldLabels).reduce(
    (text, [key, label]) => text.replace(new RegExp(key, 'gi'), label),
    value,
  )
}

export const operationLabels: Record<string, string> = {
  create_ticket: '工单登记',
  edit_ticket: '编辑工单',
  assign_ticket: '指派工单',
  cancel_ticket: '取消工单',
  reopen_ticket: '重新开启',
  save_reply_draft: '保存回复草稿',
  close_ticket: '结案归档',
  reject_human_confirm: '退回人工处理',
  status_change: '状态流转',
}

export function operationLabel(operation?: string) {
  const name = operation || ''
  return operationLabels[name] || cleanBusinessText(name) || '处理操作'
}

export function toolBusinessLabel(toolName?: string) {
  const name = toolName || ''
  if (/coupon|benefit|权益|优惠|activity/i.test(name)) return '权益活动系统'
  if (/transaction|trade|交易|dispute|chargeback/i.test(name)) return '交易查询系统'
  if (/customer|profile|客户|资料/i.test(name)) return '客户资料系统'
  if (/card|account|卡片|账户/i.test(name)) return '卡片账户系统'
  if (/credit|征信/i.test(name)) return '征信业务系统'
  if (/application|申请/i.test(name)) return '申请进度系统'
  if (/mock/i.test(name)) return 'Mock Tools（外部系统模拟）'
  return name || '外部业务系统'
}

export function cleanBusinessText(text: string) {
  return businessText(text)
    .replace(/ticket-reply\s*\/\s*suggest\s*\/\s*\d+\s*个动作[；;]?\s*/gi, '')
    .replace(/PageTask|trace|workflow|tool|confidence|prompt/gi, '')
    .replace(/字段不足/g, '信息不足')
    .trim()
}
