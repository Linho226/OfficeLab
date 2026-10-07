<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { api, newEventId, type Attempt, type AttemptSummary, type Evaluation, type FileItem, type Scenario } from './api'

const authenticated = ref(false)
const username = ref('')
const password = ref('')
const scenario = ref<Scenario | null>(null)
const attempt = ref<Attempt | null>(null)
const evaluation = ref<Evaluation | null>(null)
const currentFolderId = ref('root')
const selectedId = ref<string | null>(null)
const action = ref<'folder' | 'file' | 'rename' | 'move'>('folder')
const value = ref('')
const destinationId = ref('')
const error = ref('')
const busy = ref(false)
const loading = ref(true)
const savedAttempts = ref<AttemptSummary[]>([])
const pendingHintId = ref<string | null>(null)

const items = computed(() => attempt.value?.checkpoint.items ?? [])
const currentFolder = computed(() => items.value.find((item) => item.id === currentFolderId.value))
const children = computed(() =>
  items.value
    .filter((item) => item.parent_id === currentFolderId.value)
    .sort((left, right) => {
      if (left.kind !== right.kind) return left.kind === 'folder' ? -1 : 1
      return left.name.localeCompare(right.name, 'fr')
    }),
)
const selectedItem = computed(() => items.value.find((item) => item.id === selectedId.value))
const folders = computed(() => items.value.filter((item) => item.kind === 'folder'))
const canGoUp = computed(() => currentFolder.value?.parent_id !== null)

onMounted(checkSession)

async function checkSession() {
  try {
    const session = await api<{ authenticated: boolean }>('/api/v1/auth/session/')
    authenticated.value = session.authenticated
    if (authenticated.value) await loadScenario()
  } catch (reason) {
    showError(reason)
  } finally {
    loading.value = false
  }
}

async function signIn() {
  await run(async () => {
    await api('/api/v1/auth/login/', {
      method: 'POST',
      body: JSON.stringify({ username: username.value, password: password.value }),
    })
    authenticated.value = true
    password.value = ''
    await loadScenario()
  })
}

async function signOut() {
  await run(async () => {
    await api('/api/v1/auth/logout/', { method: 'POST', body: '{}' })
    authenticated.value = false
    scenario.value = null
    attempt.value = null
    evaluation.value = null
    savedAttempts.value = []
    pendingHintId.value = null
  })
}

async function loadScenario() {
  const [definition, saved] = await Promise.all([
    api<Scenario>('/api/v1/scenarios/FILES-001/'),
    api<AttemptSummary[]>('/api/v1/scenarios/FILES-001/attempts/'),
  ])
  scenario.value = definition
  savedAttempts.value = saved
}

async function startAttempt() {
  await run(async () => {
    attempt.value = await api<Attempt>('/api/v1/scenarios/FILES-001/attempts/', {
      method: 'POST',
      body: '{}',
    })
    resetWorkspace()
  })
}

function resetWorkspace() {
  currentFolderId.value = attempt.value?.scenario.initial_state.root_id ?? 'root'
  selectedId.value = null
  evaluation.value = null
  pendingHintId.value = null
  value.value = ''
  destinationId.value = ''
  action.value = 'folder'
}

async function resumeAttempt(id: string) {
  await run(async () => {
    attempt.value = await api<Attempt>(`/api/v1/attempts/${id}/`)
    resetWorkspace()
    evaluation.value = attempt.value.evaluation
  })
}

async function returnToExercises() {
  await run(async () => {
    await loadScenario()
    attempt.value = null
    evaluation.value = null
    pendingHintId.value = null
  })
}

async function askHint() {
  if (!attempt.value) return
  await run(async () => {
    pendingHintId.value ??= newEventId()
    const response = await api<Pick<Attempt, 'hints' | 'hints_count'>>(
      `/api/v1/attempts/${attempt.value!.id}/hint/`, {
        method: 'POST', body: JSON.stringify({ client_event_id: pendingHintId.value }),
      },
    )
    attempt.value!.hints = response.hints
    attempt.value!.hints_count = response.hints_count
    pendingHintId.value = null
  })
}

async function performAction() {
  if (!attempt.value) return
  const selected = selectedItem.value
  let eventType = ''
  let payload: Record<string, string> = {}

  if (action.value === 'folder' || action.value === 'file') {
    if (!value.value.trim()) return setError('Saisissez un nom.')
    eventType = action.value === 'folder' ? 'folder.created' : 'file.created'
    payload = {
      item_id: newEventId(),
      parent_id: currentFolderId.value,
      name: value.value.trim(),
    }
  } else if (action.value === 'rename') {
    if (!selected || !value.value.trim()) {
      return setError('Sélectionnez un élément et saisissez son nouveau nom.')
    }
    eventType = 'item.renamed'
    payload = { item_id: selected.id, name: value.value.trim() }
  } else {
    if (!selected || !destinationId.value) {
      return setError('Sélectionnez un élément et un dossier de destination.')
    }
    eventType = 'item.moved'
    payload = { item_id: selected.id, parent_id: destinationId.value }
  }

  await run(async () => {
    const response = await api<{ checkpoint: Attempt['checkpoint'] }>(
      `/api/v1/attempts/${attempt.value!.id}/events/`,
      {
        method: 'POST',
        body: JSON.stringify({
          client_event_id: newEventId(),
          event_type: eventType,
          payload,
        }),
      },
    )
    attempt.value!.checkpoint = response.checkpoint
    selectedId.value = null
    value.value = ''
    destinationId.value = ''
  })
}

async function submitAttempt() {
  if (!attempt.value) return
  await run(async () => {
    evaluation.value = await api<Evaluation>(
      `/api/v1/attempts/${attempt.value!.id}/submit/`,
      { method: 'POST', body: '{}' },
    )
    attempt.value!.status = evaluation.value.passed ? 'passed' : 'failed'
    attempt.value!.score = evaluation.value.score
  })
}

function openItem(item: FileItem) {
  selectedId.value = item.id
  if (item.kind === 'folder') currentFolderId.value = item.id
}

function goUp() {
  if (currentFolder.value?.parent_id) {
    currentFolderId.value = currentFolder.value.parent_id
    selectedId.value = null
  }
}

async function run(operation: () => Promise<void>) {
  if (busy.value) return
  busy.value = true
  error.value = ''
  try {
    await operation()
  } catch (reason) {
    showError(reason)
  } finally {
    busy.value = false
  }
}

function setError(message: string) {
  error.value = message
}

function showError(reason: unknown) {
  error.value = reason instanceof Error ? reason.message : 'Une erreur inattendue est survenue.'
}
</script>

<template>
  <header class="site-header">
    <a class="brand" href="#main">OfficeLab <span>AI</span></a>
    <button v-if="authenticated" class="quiet-button" type="button" :disabled="busy" @click="signOut">
      Se déconnecter
    </button>
  </header>

  <main id="main">
    <p v-if="loading" role="status">Chargement de votre session…</p>
    <section v-else-if="!authenticated" class="login-card" aria-labelledby="login-title">
      <p class="eyebrow">Bienvenue dans le prototype</p>
      <h1 id="login-title">Apprendre en pratiquant</h1>
      <p>Connectez-vous avec votre compte de test pour commencer l’exercice.</p>
      <form @submit.prevent="signIn">
        <label>
          Nom d’utilisateur
          <input v-model="username" autocomplete="username" required />
        </label>
        <label>
          Mot de passe
          <input v-model="password" type="password" autocomplete="current-password" required />
        </label>
        <button class="primary-button" :disabled="busy">Se connecter</button>
      </form>
    </section>

    <template v-else>
      <section v-if="scenario && !attempt" class="intro-card">
        <p class="eyebrow">Exercice pratique · {{ scenario.code }}</p>
        <h1>{{ scenario.title }}</h1>
        <ol>
          <li v-for="instruction in scenario.instructions" :key="instruction">{{ instruction }}</li>
        </ol>
        <section v-if="savedAttempts.length" aria-labelledby="saved-title" class="saved-attempts">
          <h2 id="saved-title">Vos exercices en cours</h2>
          <p>Retrouvez vos fichiers sauvegardés et les indices déjà consultés.</p>
          <ul>
            <li v-for="saved in savedAttempts" :key="saved.id">
              <button class="secondary-button" :disabled="busy" @click="resumeAttempt(saved.id)">
                Reprendre · {{ new Date(saved.updated_at).toLocaleString('fr-FR') }}
              </button>
            </li>
          </ul>
        </section>
        <button class="primary-button" :disabled="busy" @click="startAttempt">
          {{ savedAttempts.length ? 'Commencer un nouvel exercice' : 'Commencer l’exercice' }}
        </button>
      </section>

      <section v-if="attempt" class="workspace" aria-labelledby="exercise-title">
        <aside class="instructions">
          <p class="eyebrow">Votre mission</p>
          <h1 id="exercise-title">{{ attempt.scenario.title }}</h1>
          <ol>
            <li v-for="instruction in attempt.scenario.instructions" :key="instruction">{{ instruction }}</li>
          </ol>
          <div class="status-card">
            <span>État</span>
            <strong>{{ attempt.status === 'in_progress' ? 'En cours' : 'Terminée' }}</strong>
          </div>
          <button
            class="primary-button"
            :disabled="busy || attempt.status !== 'in_progress'"
            @click="submitAttempt"
          >
            Valider mon travail
          </button>
          <section class="hint-panel" aria-labelledby="hint-title">
            <h2 id="hint-title">Besoin d’aide ?</h2>
            <p>{{ attempt.hints.length }} indice(s) consulté(s) sur {{ attempt.hints_count }}. Aucun point retiré.</p>
            <ol aria-live="polite" aria-relevant="additions">
              <li v-for="hint in attempt.hints" :key="hint.level">{{ hint.text }}</li>
            </ol>
            <button class="secondary-button" :disabled="busy || attempt.status !== 'in_progress' || attempt.hints.length >= attempt.hints_count" @click="askHint">
              {{ attempt.hints.length >= attempt.hints_count ? 'Tous les indices sont affichés' : 'Afficher un indice' }}
            </button>
          </section>
          <p>Chaque action confirmée est sauvegardée automatiquement.</p>
          <button class="quiet-button" :disabled="busy" @click="returnToExercises">Revenir aux exercices</button>
        </aside>

        <div class="file-manager">
          <div class="window-bar">
            <div>
              <p class="window-title">Mes fichiers</p>
              <p class="path">Accueil / {{ currentFolder?.name }}</p>
            </div>
            <button class="quiet-button" :disabled="!canGoUp" @click="goUp">Dossier parent</button>
          </div>

          <div class="action-panel" aria-label="Actions sur les fichiers">
            <label>
              Action
              <select v-model="action">
                <option value="folder">Nouveau dossier</option>
                <option value="file">Nouveau fichier</option>
                <option value="rename">Renommer la sélection</option>
                <option value="move">Déplacer la sélection</option>
              </select>
            </label>
            <label v-if="action !== 'move'">
              {{ action === 'rename' ? 'Nouveau nom' : 'Nom' }}
              <input v-model="value" :disabled="attempt.status !== 'in_progress'" />
            </label>
            <label v-else>
              Destination
              <select v-model="destinationId">
                <option value="">Choisir un dossier</option>
                <option v-for="folder in folders" :key="folder.id" :value="folder.id">
                  {{ folder.name }}
                </option>
              </select>
            </label>
            <button
              class="secondary-button"
              :disabled="busy || attempt.status !== 'in_progress'"
              @click="performAction"
            >
              Appliquer
            </button>
          </div>

          <p class="selection" aria-live="polite">
            {{ selectedItem ? `Sélection : ${selectedItem.name}` : 'Aucun élément sélectionné' }}
          </p>

          <div class="file-grid" role="list" aria-label="Contenu du dossier">
            <button
              v-for="item in children"
              :key="item.id"
              class="file-item"
              :class="{ selected: selectedId === item.id }"
              role="listitem"
              @click="selectedId = item.id"
              @dblclick="openItem(item)"
              @keydown.enter="openItem(item)"
            >
              <span class="file-icon" aria-hidden="true">{{ item.kind === 'folder' ? '▰' : '▤' }}</span>
              <span>{{ item.name }}</span>
              <small>{{ item.kind === 'folder' ? 'Dossier' : 'Fichier texte' }}</small>
            </button>
            <p v-if="children.length === 0" class="empty-state">Ce dossier est vide.</p>
          </div>
        </div>
      </section>

      <section v-if="evaluation" class="result-card" aria-live="polite">
        <p class="eyebrow">Résultat</p>
        <h2>{{ evaluation.passed ? 'Exercice réussi' : 'Continuez vos efforts' }}</h2>
        <p class="score">{{ evaluation.score }}<span>/100</span></p>
        <ul>
          <li v-for="criterion in evaluation.criteria" :key="criterion.code">
            <strong>{{ criterion.passed ? 'Réussi' : 'À corriger' }}</strong>
            — {{ criterion.points_awarded }}/{{ criterion.points_available }} points
            <span v-if="criterion.feedback"> · {{ criterion.feedback }}</span>
          </li>
        </ul>
        <button class="secondary-button" :disabled="busy" @click="returnToExercises">Revenir aux exercices</button>
      </section>
    </template>

    <p v-if="error" class="error-message" role="alert">{{ error }}</p>
  </main>
</template>
