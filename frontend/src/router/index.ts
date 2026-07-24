import { createRouter, createWebHistory } from 'vue-router';

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: '/',
      name: 'Workbench',
      component: () => import('../views/EnterpriseTicketShellView.vue'),
    },
    {
      path: '/dispatch',
      name: 'Dispatch',
      component: () => import('../views/EnterpriseTicketShellView.vue'),
    },
    {
      path: '/dispatch/:category',
      name: 'DispatchCategory',
      component: () => import('../views/EnterpriseTicketShellView.vue'),
      props: true,
    },
    {
      path: '/reply',
      name: 'Reply',
      component: () => import('../views/EnterpriseTicketShellView.vue'),
    },
    {
      path: '/reply/:category',
      name: 'ReplyCategory',
      component: () => import('../views/EnterpriseTicketShellView.vue'),
      props: true,
    },
    {
      path: '/reply/tickets/:id',
      name: 'ReplyTicketDetail',
      component: () => import('../views/EnterpriseTicketShellView.vue'),
      props: true,
    },
    {
      path: '/tickets',
      name: 'TicketList',
      redirect: '/reply',
    },
    {
      path: '/tickets/:id',
      name: 'TicketDetail',
      redirect: to => `/reply/tickets/${to.params.id}`,
    },
    {
      path: '/legacy/tickets',
      name: 'LegacyTicketList',
      component: () => import('../views/LegacyTicketListView.vue'),
    },
    {
      path: '/legacy/tickets/:id',
      name: 'LegacyTicketDetail',
      component: () => import('../views/LegacyTicketDetailView.vue'),
      props: true,
    },
  ],
});

export default router;
