import { createRouter, createWebHistory } from 'vue-router'
import BackendView from './views/BackendView.vue'
import FavoritesView from './views/FavoritesView.vue'
import HomeView from './views/HomeView.vue'

export default createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', name: 'home', component: HomeView },
    { path: '/products', name: 'products', component: HomeView },
    { path: '/favorites', name: 'favorites', component: FavoritesView },
    { path: '/backend', redirect: { name: 'backend-instant' } },
    { path: '/backend/instant', name: 'backend-instant', component: BackendView },
    { path: '/backend/scheduled', name: 'backend-scheduled', component: BackendView },
  ],
})
