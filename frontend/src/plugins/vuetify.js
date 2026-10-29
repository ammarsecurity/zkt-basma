import 'vuetify/styles'
import { createVuetify } from 'vuetify'
import { ar } from 'vuetify/locale'
import { h } from 'vue'

const materialSymbols = {
  component: (props) =>
    h(
      'span',
      {
        class: ['material-symbols-rounded', props.class],
        'aria-hidden': 'true',
      },
      props.icon,
    ),
}

const aliases = {
  collapse: 'expand_less',
  complete: 'check',
  cancel: 'cancel',
  close: 'close',
  delete: 'cancel',
  clear: 'cancel',
  success: 'check_circle',
  info: 'info',
  warning: 'warning',
  error: 'error',
  prev: 'chevron_left',
  next: 'chevron_right',
  checkboxOn: 'check_box',
  checkboxOff: 'check_box_outline_blank',
  checkboxIndeterminate: 'indeterminate_check_box',
  delimiter: 'circle',
  sortAsc: 'arrow_upward',
  sortDesc: 'arrow_downward',
  expand: 'expand_more',
  menu: 'menu',
  subgroup: 'arrow_drop_down',
  dropdown: 'arrow_drop_down',
  radioOn: 'radio_button_checked',
  radioOff: 'radio_button_unchecked',
  edit: 'edit',
  ratingEmpty: 'star',
  ratingFull: 'star',
  ratingHalf: 'star_half',
  loading: 'progress_activity',
  first: 'first_page',
  last: 'last_page',
  unfold: 'unfold_more',
  file: 'attach_file',
  plus: 'add',
  minus: 'remove',
  calendar: 'calendar_month',
  treeviewCollapse: 'arrow_drop_down',
  treeviewExpand: 'chevron_left',
  eyeDropper: 'colorize',
  sort: 'sort',
}

export default createVuetify({
  locale: {
    locale: 'ar',
    fallback: 'ar',
    messages: { ar },
    rtl: { ar: true },
  },
  icons: {
    defaultSet: 'ms',
    aliases,
    sets: { ms: materialSymbols },
  },
  theme: {
    defaultTheme: 'light',
    themes: {
      light: {
        colors: {
          primary: '#2563EB',
          secondary: '#475569',
          success: '#22C55E',
          warning: '#F59E0B',
          error: '#EF4444',
          background: '#F8FAFC',
          surface: '#FFFFFF',
          'on-surface': '#0F172A',
          'on-background': '#0F172A',
        },
      },
    },
  },
  defaults: {
    VBtn: {
      elevation: 0,
      rounded: 'lg',
    },
    VCard: {
      elevation: 0,
      rounded: 'lg',
    },
    VTextField: {
      variant: 'outlined',
      density: 'comfortable',
      hideDetails: 'auto',
      color: 'primary',
    },
    VSelect: {
      variant: 'outlined',
      density: 'comfortable',
      hideDetails: 'auto',
      color: 'primary',
    },
  },
})
