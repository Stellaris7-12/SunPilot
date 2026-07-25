import { createRouter, createWebHistory } from 'vue-router'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: '/',
      name: 'Workbench',
      component: () => import('../pages/workbench/WorkbenchPage.vue'),
    },
    {
      path: '/dispatch',
      name: 'Dispatch',
      component: () => import('../pages/dispatch/DispatchPage.vue'),
    },
    {
      path: '/dispatch/:category',
      name: 'DispatchCategory',
      component: () => import('../pages/dispatch/DispatchCategoryPage.vue'),
      props: true,
    },
    {
      path: '/reply',
      name: 'Reply',
      component: () => import('../pages/reply/ReplyQueuePage.vue'),
    },
    {
      path: '/reply/:category',
      name: 'ReplyCategory',
      component: () => import('../pages/reply/ReplyCategoryPage.vue'),
      props: true,
    },
    {
      path: '/reply/tickets/:id',
      name: 'ReplyTicketDetail',
      component: () => import('../pages/reply/ReplyTicketPage.vue'),
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
  ],
})

export default router
