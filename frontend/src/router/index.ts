import { createRouter, createWebHistory } from 'vue-router';

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: '/',
      redirect: '/tickets'
    },
    {
      path: '/tickets',
      name: 'TicketList',
      component: () => import('../views/TicketListView.vue'),
    },
    {
      path: '/tickets/:id',
      name: 'TicketDetail',
      component: () => import('../views/TicketDetailView.vue'),
      props: true,
    },
  ],
});

export default router;
