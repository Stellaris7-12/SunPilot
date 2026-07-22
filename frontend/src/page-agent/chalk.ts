type ChalkFn = ((text: string) => string) & {
  bold: (text: string) => string
}

function passthrough(text: string) {
  return text
}

const color = passthrough as ChalkFn
color.bold = passthrough

export default {
  blue: color,
  green: color,
  gray: color,
  red: color,
  yellow: color,
  cyan: passthrough,
}
