<script setup>
import {computed, onMounted, onUnmounted, ref, watch} from 'vue';
import {
  BarChart3,
  Bell,
  BookOpen,
  CheckCircle2,
  ChevronDown,
  LayoutDashboard,
  MessageSquare,
  Search,
  Settings,
  Ticket,
  Users,
  Workflow,
} from '@lucide/vue';
import {
  getApprovals,
  getBackendHealth,
  getOperationsOverview,
  getTickets,
  revokeSession,
} from './api.js';
import {toWorkspaceTicket} from './lib/format.js';
import AccountCenter from './views/AccountCenter.vue';
import AnalyticsWorkspace from './views/AnalyticsWorkspace.vue';
import ApprovalsView from './views/ApprovalsView.vue';
import CustomerView from './views/CustomerView.vue';
import KnowledgeWorkspace from './views/KnowledgeWorkspace.vue';
import ModelSettings from './views/ModelSettings.vue';
import OverviewView from './views/OverviewView.vue';
import TicketsView from './views/TicketsView.vue';
import GuestGate from './components/GuestGate.vue';

const props = defineProps({
  session: {type: Object, default: null},
});
const emit = defineEmits(['signed-in']);

const navEntries = [
  ['概览', 'overview', LayoutDashboard],
  ['工单', 'tickets', Ticket],
  ['客户', 'customers', Users],
  ['知识库', 'knowledge', BookOpen],
  ['自动化', 'automation', Workflow],
  ['分析', 'analytics', BarChart3],
  ['设置', 'settings', Settings],
];
const agentNav = navEntries.filter(([, key]) => key !== 'customers');
const customerNav = [['我的服务', 'customers', Users]];

const role = computed(() => props.session?.role);
const landingPage = () => (props.session ? (role.value === 'CUSTOMER' ? 'customers' : 'overview') : 'account');

const page = ref(landingPage());
const profile = ref(null);
const selected = ref(null);
const notice = ref('');
const overview = ref(null);
const workspaceTickets = ref([]);
const ticketsLoaded = ref(role.value === 'CUSTOMER');
const pendingApprovals = ref([]);
const searchQuery = ref('');
const searchOpen = ref(false);
const notificationOpen = ref(false);
const messageOpen = ref(false);
const accountMenuOpen = ref(false);
const backendStatus = ref('checking');
const searchInput = ref(null);

// 非渲染态的可变引用：与 React 的 useRef 占位等价。
let previousPage = landingPage();
let justSignedIn = false;
let healthTimer = null;

const nav = computed(() => (role.value === 'CUSTOMER' ? customerNav : agentNav));

const checkBackend = async ({retryInDesktop = false, silent = false} = {}) => {
  if (!silent) backendStatus.value = 'checking';
  try {
    await getBackendHealth();
    backendStatus.value = 'connected';
  } catch {
    // 打包版里内嵌后端可能首启失败：仅在用户主动重新检测时，先触发
    // Tauri 侧的重启命令，再复查一次；静默轮询不做重启。
    if (retryInDesktop && globalThis.__TAURI_INTERNALS__) {
      try {
        await globalThis.__TAURI_INTERNALS__.invoke('restart_backend');
        await getBackendHealth();
        backendStatus.value = 'connected';
        return;
      } catch {}
    }
    backendStatus.value = 'disconnected';
  }
};

onMounted(() => {
  checkBackend();
  healthTimer = setInterval(() => checkBackend({silent: true}), 20000);
  window.addEventListener('keydown', handleShortcut);
});

onUnmounted(() => {
  clearInterval(healthTimer);
  window.removeEventListener('keydown', handleShortcut);
});

// 会话变化时的落位：退出登录回到个人中心；登录成功进入对应工作台首页。
watch(() => props.session, () => {
  if (!props.session) {
    page.value = 'account';
    return;
  }
  if (justSignedIn) {
    justSignedIn = false;
    page.value = props.session.role === 'CUSTOMER' ? 'customers' : 'overview';
  }
});

watch([() => props.session, role], () => {
  if (!props.session || role.value === 'CUSTOMER') return;
  getOperationsOverview().then(value => {overview.value = value;}).catch(error => {notice.value = error.message;});
}, {immediate: true});

watch([() => props.session, role], () => {
  if (!props.session || role.value === 'CUSTOMER') return;
  getTickets()
    .then(items => {
      const normalized = items.map(toWorkspaceTicket);
      workspaceTickets.value = normalized;
      selected.value = normalized[0] || null;
    })
    .catch(error => {
      workspaceTickets.value = [];
      selected.value = null;
      notice.value = error.message;
    })
    .finally(() => {ticketsLoaded.value = true;});
}, {immediate: true});

watch([() => props.session, role], () => {
  if (!props.session || role.value === 'CUSTOMER') return;
  getApprovals()
    .then(items => {pendingApprovals.value = items.filter(item => item.status === 'PENDING');})
    .catch(error => {notice.value = error.message;});
}, {immediate: true});

const handleShortcut = event => {
  if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === 'k' && props.session && role.value !== 'CUSTOMER') {
    event.preventDefault();
    searchOpen.value = true;
    searchInput.value?.focus();
  }
  if ((event.metaKey || event.ctrlKey) && event.key === ',') {
    event.preventDefault();
    if (page.value === 'account') {
      page.value = previousPage || landingPage();
    } else {
      previousPage = page.value;
      page.value = 'account';
    }
    notice.value = '';
  }
};

const navTo = key => {
  if (key === 'account') {
    accountMenuOpen.value = !accountMenuOpen.value;
    return;
  }
  if (page.value !== 'account') previousPage = page.value;
  page.value = key;
  notice.value = '';
};

const handleSignedIn = signedIn => {
  justSignedIn = Boolean(signedIn);
  emit('signed-in', signedIn);
};

const handleLogout = () => {
  revokeSession(localStorage.getItem('supportflow.refreshToken'));
  localStorage.removeItem('supportflow.accessToken');
  localStorage.removeItem('supportflow.refreshToken');
  accountMenuOpen.value = false;
  emit('signed-in', null);
};

const normalizedSearch = computed(() => searchQuery.value.trim().toLocaleLowerCase());
const searchResults = computed(() => (normalizedSearch.value
  ? workspaceTickets.value
    .filter(ticket => [ticket.id, ticket.title, ticket.customer, ticket.status, ticket.priority]
      .some(value => String(value).toLocaleLowerCase().includes(normalizedSearch.value)))
    .slice(0, 6)
  : []));
const displayInitials = computed(() => (props.session ? (profile.value?.displayName || '账户') : '访').trim().slice(0, 2).toLocaleUpperCase());
const accountName = computed(() => (props.session ? (profile.value?.displayName || '个人中心') : '未登录'));
const activeTicketCount = computed(() => (ticketsLoaded.value
  ? workspaceTickets.value.filter(ticket => !['RESOLVED', 'CLOSED'].includes(ticket.statusCode) && !['已解决', '已关闭'].includes(ticket.status)).length
  : 0));
const notificationCount = computed(() => activeTicketCount.value + pendingApprovals.value.length);

const openTicket = ticket => {
  selected.value = ticket;
  page.value = 'tickets';
  searchQuery.value = '';
  searchOpen.value = false;
  notice.value = '';
};

const handleSearchKeyDown = event => {
  if (event.key === 'Escape') {
    searchQuery.value = '';
    searchOpen.value = false;
    event.currentTarget.blur();
  }
  if (event.key === 'Enter' && searchResults.value.length) {
    event.preventDefault();
    openTicket(searchResults.value[0]);
  }
};

const handleSearchBlur = event => {
  if (!event.currentTarget.contains(event.relatedTarget)) searchOpen.value = false;
};

// 子组件提交原始工单对象，归一化与两处状态更新集中在这里，等价于 React 版 updateTicket。
const handleTicketUpdated = rawTicket => {
  const normalized = toWorkspaceTicket(rawTicket);
  workspaceTickets.value = workspaceTickets.value.map(item => (item.rawId === normalized.rawId ? normalized : item));
  selected.value = normalized;
};
</script>

<template>
  <div class="app-shell">
    <header class="topbar">
      <div class="brand"><span class="brand-mark">◉</span><span>SupportFlow AI</span></div>
      <div v-if="session && role !== 'CUSTOMER'" class="global-search" @focusout="handleSearchBlur">
        <Search :size="17" />
        <input
          ref="searchInput"
          aria-label="全局搜索工单"
          role="combobox"
          :aria-expanded="String(searchOpen && Boolean(normalizedSearch))"
          aria-controls="global-ticket-search-results"
          :value="searchQuery"
          placeholder="搜索工单编号、标题、客户…"
          @focus="searchOpen = true"
          @input="searchQuery = $event.target.value; searchOpen = true"
          @keydown="handleSearchKeyDown"
        />
        <kbd>⌘ K</kbd>
        <div v-if="searchOpen && normalizedSearch" id="global-ticket-search-results" class="global-search-results" role="listbox">
          <button
            v-for="ticket in searchResults"
            :key="ticket.id"
            role="option"
            aria-selected="false"
            @mousedown.prevent
            @click="openTicket(ticket)"
          >
            <span><strong>{{ ticket.id }}</strong>{{ ticket.title }}</span>
            <small>{{ ticket.customer }} · {{ ticket.status }} · {{ ticket.priority }}</small>
          </button>
          <p v-if="!searchResults.length">没有匹配的工单</p>
        </div>
      </div>
      <div class="top-actions">
        <div v-if="session" class="top-action-popover">
          <button
            class="top-icon-button"
            aria-label="查看通知"
            :aria-expanded="String(notificationOpen)"
            @click="notificationOpen = !notificationOpen; messageOpen = false"
          >
            <Bell :size="19" /><span v-if="notificationCount > 0" class="notification-count">{{ notificationCount }}</span>
          </button>
          <div v-if="notificationOpen" class="top-popover">
            <strong>待处理</strong>
            <p>{{ notificationCount ? `当前工作区有 ${notificationCount} 条待处理事项` : '当前工作区暂无待处理事项' }}</p>
            <small v-if="pendingApprovals.length > 0">其中 {{ pendingApprovals.length }} 条等待审批</small>
            <small v-if="activeTicketCount > 0">{{ activeTicketCount }} 个未关闭工单</small>
            <button @click="notificationOpen = false; navTo('automation')">查看审批与提醒</button>
          </div>
        </div>
        <div v-if="session" class="top-action-popover">
          <button
            class="top-icon-button"
            aria-label="查看消息"
            :aria-expanded="String(messageOpen)"
            @click="messageOpen = !messageOpen; notificationOpen = false"
          >
            <MessageSquare :size="19" />
          </button>
          <div v-if="messageOpen" class="top-popover">
            <strong>消息</strong>
            <p>暂无未读会话消息</p>
            <small>新的客户回复会显示在工单会话中。</small>
            <button @click="messageOpen = false; navTo('tickets')">打开工单会话</button>
          </div>
        </div>
        <div :class="backendStatus === 'connected' ? 'online' : 'online offline'" role="status">
          <i></i>{{ backendStatus === 'connected' ? '在线' : backendStatus === 'checking' ? '检测中' : '服务离线' }}
        </div>
        <button class="account-menu-trigger" aria-label="打开个人中心" @click="navTo('account')">
          <div class="avatar">{{ displayInitials }}</div>
          <span>{{ accountName }}</span>
          <kbd class="topbar-shortcut-badge">⌘ ,</kbd>
          <ChevronDown :size="16" />
        </button>
      </div>
    </header>
    <div class="workspace">
      <aside class="sidebar">
        <nav>
          <button
            v-for="[label, key, Icon] in nav"
            :key="key"
            :class="page === key ? 'active' : ''"
            @click="navTo(key)"
          >
            <component :is="Icon" :size="19" /><span>{{ label }}</span><b v-if="key === 'tickets'">{{ workspaceTickets.length }}</b>
          </button>
        </nav>
        <div class="vector-health">
          <div class="health-title">向量存储健康度 <CheckCircle2 :size="15" /></div>
          <strong>按知识库查看</strong>
          <p>实时状态请进入知识库管理</p>
          <div class="progress"><span :style="{width: '100%'}"></span></div>
        </div>
        <button :class="page === 'account' ? 'tenant active' : 'tenant'" @click="navTo('account')">
          <div class="avatar">{{ displayInitials }}</div>
          <div>
            <strong>{{ profile?.tenantName || (session ? '当前工作区' : '未登录') }}</strong>
            <small>{{ profile?.role || session?.role || '点击前往登录' }}</small>
          </div>
          <ChevronDown :size="16" />
        </button>
      </aside>
      <main class="main-content">
        <AccountCenter
          v-if="page === 'account'"
          :session="session"
          :backend-status="backendStatus"
          @notice="notice = $event"
          @profile-change="profile = $event"
          @open-model-settings="navTo('settings')"
          @recheck-backend="checkBackend({retryInDesktop: true})"
          @signed-in="handleSignedIn"
        />
        <GuestGate v-else-if="!session" @go-account="navTo('account')" />
        <template v-else>
          <OverviewView v-if="page === 'overview'" :overview="overview" :tickets="workspaceTickets" @nav="navTo" />
          <KnowledgeWorkspace v-if="page === 'knowledge'" @notice="notice = $event" />
          <TicketsView
            v-if="page === 'tickets'"
            v-model:selected="selected"
            :tickets="workspaceTickets"
            @ticket-updated="handleTicketUpdated"
            @notice="notice = $event"
          />
          <CustomerView v-if="page === 'customers'" />
          <AnalyticsWorkspace v-if="page === 'analytics'" :overview="overview" />
          <ModelSettings v-if="page === 'settings'" @notice="notice = $event" />
          <ApprovalsView v-if="page === 'automation'" @notice="notice = $event" />
        </template>
      </main>
    </div>
    <div v-if="accountMenuOpen" class="account-dropdown" role="menu">
      <button role="menuitem" @click="accountMenuOpen = false; page = 'account'">个人中心</button>
      <button role="menuitem" @click="accountMenuOpen = false; page = 'settings'">设置</button>
      <button v-if="session" role="menuitem" @click="handleLogout">退出登录</button>
      <button v-else role="menuitem" @click="accountMenuOpen = false; page = 'account'">前往登录</button>
    </div>
    <div v-if="notice" class="toast"><CheckCircle2 :size="17" />{{ notice }}</div>
  </div>
</template>
