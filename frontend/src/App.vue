<script setup lang="ts">
import { computed, nextTick, onMounted, ref } from 'vue'
import { api, ApiError, newEventId, type Attempt, type AttemptSummary, type Evaluation, type Mission } from './api'
import FileExplorer from './components/FileExplorer.vue'
import LabIcon from './components/LabIcon.vue'

const authenticated = ref(false)
const username = ref('')
const password = ref('')
const displayName = ref('')
const loading = ref(true)
const busy = ref(false)
const error = ref('')
const message = ref('')
const missions = ref<Mission[]>([])
const saved = ref<AttemptSummary[]>([])
const attempt = ref<Attempt | null>(null)
const evaluation = ref<Evaluation | null>(null)
const pendingHintId = ref<string | null>(null)
const pendingEvent = ref<{ client_event_id: string; event_type: string; payload: Record<string, string> } | null>(null)
const restartDialog = ref<HTMLDialogElement | null>(null)
const feedback = ref<HTMLElement | null>(null)
const currentMission = computed(() => missions.value.find(mission => mission.code === attempt.value?.scenario.code))
const completed = computed(() => missions.value.filter(mission => mission.passed).length)
const totalPoints = computed(() => missions.value.reduce((total, mission) => total + (mission.best_score ?? 0), 0))
const nextMission = computed(() => {
  const index = missions.value.findIndex(mission => mission.code === attempt.value?.scenario.code)
  return index >= 0 ? missions.value[index + 1] : undefined
})
const editable = computed(() => attempt.value?.status === 'in_progress')

async function run(operation: () => Promise<void>) {
  if (busy.value) return false
  busy.value = true; error.value = ''
  try { await operation(); return true }
  catch (reason) { error.value = reason instanceof Error ? reason.message : 'Une erreur est survenue. Réessayez.'; return false }
  finally { busy.value = false }
}
async function loadHome() {
  const [catalog, attempts] = await Promise.all([
    api<Mission[]>('/api/v1/scenarios/'), api<AttemptSummary[]>('/api/v1/attempts/'),
  ])
  missions.value = catalog; saved.value = attempts
}
onMounted(async () => {
  await run(async () => {
    const session = await api<{ authenticated: boolean; user?: { username: string } }>('/api/v1/auth/session/')
    authenticated.value = session.authenticated
    displayName.value = session.user?.username ?? ''
    if (authenticated.value) await loadHome()
  })
  loading.value = false
})
async function signIn() {
  await run(async () => {
    const session = await api<{ user: { username: string } }>('/api/v1/auth/login/', {
      method: 'POST', body: JSON.stringify({ username: username.value, password: password.value }),
    })
    authenticated.value = true; displayName.value = session.user.username; password.value = ''
    await loadHome()
  })
}
async function signOut() {
  await run(async () => {
    await api('/api/v1/auth/logout/', { method: 'POST', body: '{}' })
    authenticated.value = false; attempt.value = null; evaluation.value = null
    missions.value = []; saved.value = []; pendingEvent.value = null; pendingHintId.value = null; message.value = ''
  })
}
function setAttempt(value: Attempt) {
  attempt.value = value; evaluation.value = value.evaluation
  pendingEvent.value = null; pendingHintId.value = null; message.value = ''
}
async function chooseMission(mission: Mission) {
  if (attempt.value?.scenario.code === mission.code) return
  await run(async () => {
    const value = mission.resume_id
      ? await api<Attempt>(`/api/v1/attempts/${mission.resume_id}/`)
      : await api<Attempt>(`/api/v1/scenarios/${mission.code}/attempts/`, { method: 'POST', body: '{}' })
    setAttempt(value)
    await loadHome()
  })
}
async function resume(id: string) {
  await run(async () => { setAttempt(await api<Attempt>(`/api/v1/attempts/${id}/`)) })
}
async function home() {
  await run(async () => { await loadHome(); attempt.value = null; evaluation.value = null; pendingEvent.value = null; message.value = '' })
}
async function perform(type: string, payload: Record<string, string>) {
  if (!attempt.value || !editable.value) return false
  if (pendingEvent.value) {
    error.value = 'Une action attend confirmation. Utilisez « Réessayer l’action » avant de continuer.'
    return false
  }
  pendingEvent.value = { client_event_id: newEventId(), event_type: type, payload }
  return sendPendingEvent()
}
async function sendPendingEvent() {
  if (!attempt.value || !pendingEvent.value) return false
  return run(async () => {
    try {
      const response = await api<{ checkpoint: Attempt['checkpoint'] }>(`/api/v1/attempts/${attempt.value!.id}/events/`, {
        method: 'POST', body: JSON.stringify(pendingEvent.value),
      })
      attempt.value!.checkpoint = response.checkpoint
      pendingEvent.value = null; evaluation.value = null; message.value = 'Modification sauvegardée'
    } catch (reason) {
      if (reason instanceof ApiError && reason.status >= 400 && reason.status < 500) pendingEvent.value = null
      throw reason
    }
  })
}
async function askHint() {
  if (!attempt.value) return
  await run(async () => {
    pendingHintId.value ??= newEventId()
    try {
      const result = await api<Pick<Attempt, 'hints' | 'hints_count'>>(`/api/v1/attempts/${attempt.value!.id}/hint/`, {
        method: 'POST', body: JSON.stringify({ client_event_id: pendingHintId.value }),
      })
      attempt.value!.hints = result.hints; attempt.value!.hints_count = result.hints_count
      pendingHintId.value = null
    } catch (reason) {
      if (reason instanceof ApiError && reason.status >= 400 && reason.status < 500) pendingHintId.value = null
      throw reason
    }
  })
}
async function check() {
  if (!attempt.value) return
  await run(async () => {
    evaluation.value = await api<Evaluation>(`/api/v1/attempts/${attempt.value!.id}/check/`, { method: 'POST', body: '{}' })
    await nextTick(); feedback.value?.focus()
  })
}
async function finish() {
  if (!attempt.value) return
  await run(async () => {
    const result = await api<Evaluation>(`/api/v1/attempts/${attempt.value!.id}/submit/`, { method: 'POST', body: '{}' })
    evaluation.value = result
    attempt.value!.status = result.passed ? 'passed' : 'failed'; attempt.value!.score = result.score
    await loadHome(); await nextTick(); feedback.value?.focus()
  })
}
async function restart() {
  if (!attempt.value) return
  if (await run(async () => {
    setAttempt(await api<Attempt>(`/api/v1/attempts/${attempt.value!.id}/restart/`, { method: 'POST', body: '{}' }))
    await loadHome()
  })) restartDialog.value?.close()
}
</script>

<template>
  <header class="site-header">
    <a class="brand" href="#main" @click.prevent="authenticated && !busy ? home() : undefined"><span class="brand-symbol"><LabIcon name="book" :size="23" /></span><span>Office<span class="brand-light">Lab</span><small>APPRENDRE PAR LA PRATIQUE</small></span></a>
    <span class="header-course">L’atelier numérique <span>/</span> Les essentiels</span>
    <div v-if="authenticated" class="account"><span class="avatar">{{ displayName.slice(0, 1).toUpperCase() }}</span><span class="account-name">{{ displayName }}</span><button class="icon-button" :disabled="busy" title="Se déconnecter" aria-label="Se déconnecter" @click="signOut"><LabIcon name="logout" /></button></div>
    <span v-else class="header-course">Un geste à la fois.</span>
  </header>
  <main id="main" :aria-busy="busy">
    <p v-if="loading" class="loading" role="status">Préparation de votre espace…</p>
    <section v-else-if="!authenticated" class="login-card">
      <span class="eyebrow">BIENVENUE DANS VOTRE ATELIER</span><h1>Les bons gestes<br>commencent ici.</h1><p>Un espace pour essayer, comprendre et gagner en autonomie.</p>
      <form @submit.prevent="signIn"><label for="username">Nom d’utilisateur</label><input id="username" v-model="username" autocomplete="username" required /><label for="password">Mot de passe</label><input id="password" v-model="password" type="password" autocomplete="current-password" required /><button class="primary-button" :disabled="busy">Se connecter <LabIcon name="arrow" :size="17" /></button></form>
    </section>
    <template v-else>
      <div class="page-heading"><div class="page-title"><span class="page-icon"><LabIcon name="folder" :size="30" /></span><div><p class="eyebrow">LES ESSENTIELS · FICHIERS & DOSSIERS</p><h1>L’explorateur de fichiers</h1><p>Organisez, renommez, déplacez. Apprenez en faisant.</p></div></div><div class="heading-actions"><span class="saved-label" role="status"><span class="status-dot"></span>{{ busy ? 'En cours…' : message || 'Progression sauvegardée' }}</span><button v-if="attempt" class="secondary-button" :disabled="busy || !!pendingEvent" @click="restartDialog?.showModal()"><LabIcon name="reset" :size="17" />Recommencer</button></div></div>
      <nav class="mission-tabs" aria-label="Missions du parcours"><button v-for="mission in missions" :key="mission.code" :class="{ active: attempt?.scenario.code === mission.code, complete: mission.passed }" :aria-current="attempt?.scenario.code === mission.code ? 'step' : undefined" :disabled="busy || !!pendingEvent" @click="chooseMission(mission)"><span class="tab-number"><LabIcon v-if="mission.passed" name="check" :size="14" /><template v-else>{{ mission.order.toString().padStart(2, '0') }}</template></span><span>{{ mission.title }}</span></button><span class="course-progress">{{ completed }}/{{ missions.length }} missions réussies</span></nav>
      <section v-if="!attempt" class="course-home">
        <div class="home-intro"><span class="eyebrow">VOTRE PARCOURS</span><h2>Une place pour chaque fichier.</h2><p>Trois missions pour prendre vos repères. Vous pouvez vérifier votre travail et réessayer autant que nécessaire.</p><span class="points-pill">{{ totalPoints }} / {{ missions.length * 100 }} points</span></div>
        <div class="mission-cards"><article v-for="mission in missions" :key="mission.code" class="mission-card"><div class="card-top"><span class="card-number">0{{ mission.order }}</span><span class="mission-tag">{{ mission.passed ? 'Réussie' : mission.resume_id ? 'En cours' : 'À découvrir' }}</span></div><LabIcon :name="mission.order === 1 ? 'folder' : mission.order === 2 ? 'rename' : 'desktop'" :size="35" /><h3>{{ mission.title }}</h3><p>{{ mission.instructions[0] }}</p><button class="secondary-button" :disabled="busy" @click="chooseMission(mission)">{{ mission.resume_id ? 'Reprendre' : mission.passed ? 'Rejouer' : 'Commencer' }}<LabIcon name="arrow" :size="16" /></button></article></div>
        <p v-if="!missions.length">Aucune mission n’est disponible pour le moment.</p>
        <section v-if="saved.length" class="saved-attempts"><h2>Retrouver un exercice en cours</h2><ul><li v-for="entry in saved" :key="entry.id"><span>{{ entry.title }}<small>{{ new Date(entry.updated_at).toLocaleString('fr-FR') }}</small></span><button class="text-button" :disabled="busy" @click="resume(entry.id)">Reprendre <LabIcon name="arrow" :size="15" /></button></li></ul></section>
      </section>
      <div v-else class="workspace">
        <div class="workspace-main"><FileExplorer :key="attempt.id" :attempt="attempt" :busy="busy" :perform="perform" :error="error" :pending="!!pendingEvent" :retry="sendPendingEvent" /><p class="keyboard-help"><kbd>Entrée</kbd> Ouvrir <span>·</span> <kbd>F2</kbd> Renommer <span>·</span> <kbd>Ctrl X</kbd> Couper <span>·</span> <kbd>Ctrl C</kbd> Copier <span>·</span> <kbd>Ctrl V</kbd> Coller <span class="keyboard-note">Vous pouvez aussi glisser-déposer vos fichiers.</span></p></div>
        <aside class="mission-panel" aria-labelledby="mission-title">
          <div class="mission-banner"><div><span class="level-pill">NIVEAU 1 · DÉCOUVERTE</span><span class="mission-points">{{ totalPoints }} pts</span></div><p class="mission-counter">{{ currentMission ? `MISSION ${currentMission.order} SUR ${missions.length}` : 'EXERCICE LIBRE' }}</p><h2 id="mission-title">{{ attempt.scenario.title }}</h2><div class="progress-track" role="progressbar" aria-label="Missions réussies" :aria-valuenow="completed" :aria-valuemin="0" :aria-valuemax="missions.length || 1"><span :style="{ width: `${completed / (missions.length || 1) * 100}%` }"></span></div></div>
          <div class="mission-body"><div class="objective"><h3>À vous de jouer</h3><ol><li v-for="instruction in attempt.scenario.instructions" :key="instruction">{{ instruction }}</li></ol></div>
            <div class="hint-panel"><div class="hint-heading"><LabIcon name="bulb" :size="19" /><strong>Un coup de pouce ?</strong><span>{{ attempt.hints.length }}/{{ attempt.hints_count }}</span></div><ol v-if="attempt.hints.length" aria-live="polite"><li v-for="hint in attempt.hints" :key="hint.level">{{ hint.text }}</li></ol><p v-else>Un indice pour avancer, sans perdre de points.</p><button class="text-button" :disabled="busy || !editable || attempt.hints.length >= attempt.hints_count || !!pendingEvent" @click="askHint">{{ attempt.hints.length >= attempt.hints_count ? 'Tous les indices sont affichés' : 'Afficher un indice' }}<LabIcon name="arrow" :size="14" /></button></div>
            <section v-if="evaluation" ref="feedback" class="feedback" :class="{ success: evaluation.passed }" tabindex="-1" aria-live="polite"><h3><LabIcon :name="evaluation.passed ? 'check' : 'info'" :size="19" />{{ evaluation.passed ? editable ? 'Tout est à sa place !' : 'Mission réussie !' : editable ? 'Encore un petit effort' : 'Tentative terminée' }}</h3><p class="feedback-score">{{ evaluation.score }}<small>/100</small></p><p v-if="editable">{{ evaluation.passed ? 'Vous pouvez maintenant terminer cette mission.' : 'Votre exercice reste ouvert. Corrigez puis vérifiez à nouveau.' }}</p><ul v-if="!evaluation.passed"><li v-for="criterion in evaluation.criteria.filter(c => !c.passed)" :key="criterion.code">{{ criterion.feedback }}</li></ul></section>
            <button v-if="editable" class="primary-button check-button" :disabled="busy || !!pendingEvent" @click="check"><LabIcon name="check" />Vérifier mon travail</button>
            <button v-if="editable && evaluation?.passed" class="secondary-button finish-button" :disabled="busy || !!pendingEvent" @click="finish">Terminer la mission <LabIcon name="arrow" :size="17" /></button>
            <button v-if="!editable && nextMission" class="primary-button check-button" :disabled="busy" @click="chooseMission(nextMission)">Mission suivante <LabIcon name="arrow" :size="17" /></button>
            <p v-if="editable" class="reassurance">Essayez, vérifiez, recommencez.<br>Vous êtes ici pour apprendre.</p>
            <button class="text-button home-link" :disabled="busy || !!pendingEvent" @click="home"><LabIcon name="back" :size="14" />Revenir au parcours</button>
          </div>
        </aside>
      </div>
    </template>
    <div v-if="error" class="error-message" role="alert"><strong>Impossible de terminer l’action</strong><p>{{ error }}</p><button v-if="pendingEvent" class="secondary-button" :disabled="busy" @click="sendPendingEvent">Réessayer l’action</button><button v-else class="text-button" @click="error = ''">Fermer</button></div>
    <dialog ref="restartDialog" class="action-dialog" aria-labelledby="restart-title" @cancel="busy && $event.preventDefault()"><h2 id="restart-title">Recommencer cette mission ?</h2><p>Vous repartirez de l’état initial avec de nouveaux indices. Cette tentative restera dans votre historique.</p><p v-if="error" role="alert">{{ error }}</p><div class="dialog-actions"><button class="secondary-button" :disabled="busy" @click="restartDialog?.close()">Annuler</button><button class="primary-button" :disabled="busy" @click="restart">Recommencer</button></div></dialog>
  </main>
</template>
