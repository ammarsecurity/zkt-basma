import { createApp } from 'vue'
import App from './App.vue'
import router from './router'
import vuetify from './plugins/vuetify'
import '@fontsource/cairo/400.css'
import '@fontsource/cairo/600.css'
import '@fontsource/cairo/700.css'
import 'material-symbols/rounded.css'
import './styles.css'

createApp(App).use(router).use(vuetify).mount('#app')
