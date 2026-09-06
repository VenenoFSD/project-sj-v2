import { createRouter, createWebHistory } from 'vue-router'
import BackendView from './views/BackendView.vue'
import HomeView from './views/HomeView.vue'

export default createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', name: 'home', component: HomeView },
    { path: '/backend', name: 'backend', component: BackendView },
  ],
})
