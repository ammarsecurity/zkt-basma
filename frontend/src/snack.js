import { reactive } from 'vue'

export const snack = reactive({
  show: false,
  text: '',
  color: 'success',
})

export function notify(text, color = 'success') {
  snack.text = text
  snack.color = color
  snack.show = true
}
