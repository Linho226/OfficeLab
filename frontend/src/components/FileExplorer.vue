<script setup lang="ts">
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from 'vue'
import type { Attempt, FileItem } from '../api'
import { newEventId } from '../api'
import LabIcon from './LabIcon.vue'

const props = defineProps<{
  attempt: Attempt
  busy: boolean
  error: string
  pending: boolean
  retry: () => Promise<boolean>
  perform: (type: string, payload: Record<string, string>) => Promise<boolean>
}>()
const currentId = ref(props.attempt.scenario.initial_state.root_id)
const selectedId = ref<string | null>(null)
const selectedTrashId = ref<string | null>(null)
const inTrash = ref(false)
const cutId = ref<string | null>(null)
const copiedId = ref<string | null>(null)
const dragId = ref<string | null>(null)
const dropId = ref<string | null>(null)
const view = ref<'grid' | 'list'>('grid')
const dialog = ref<HTMLDialogElement | null>(null)
const input = ref<HTMLInputElement | null>(null)
const dialogMode = ref<'folder' | 'file' | 'rename' | 'delete' | 'emptyTrash' | 'properties'>('folder')
const dialogItem = ref<FileItem | null>(null)
const name = ref('')
const context = ref<{ x: number; y: number } | null>(null)
const menu = ref<HTMLElement | null>(null)
const fileArea = ref<HTMLElement | null>(null)
let returnFocus: HTMLElement | null = null

const items = computed(() => props.attempt.checkpoint.items)
const trashEntries = computed(() =>
  Object.entries(props.attempt.checkpoint.trash ?? {})
    .map(([id, entry]) => ({
      id,
      item: entry.items[0],
      count: entry.items.length,
      originalParentId: entry.original_parent_id,
    }))
    .filter(entry => entry.item !== undefined)
)
const selectedTrash = computed(() =>
  trashEntries.value.find(entry => entry.id === selectedTrashId.value)
)
const showTrash = computed(() =>
  trashEntries.value.length > 0 ||
  ['item.trashed', 'item.restored', 'trash.emptied']
    .some(action => props.attempt.scenario.allowed_actions.includes(action))
)
const deleteAction = computed(() =>
  props.attempt.scenario.allowed_actions.includes('item.trashed')
    ? 'item.trashed'
    : 'item.deleted'
)
const root = computed(() => items.value.find(item => item.id === props.attempt.scenario.initial_state.root_id)!)
const current = computed(() => items.value.find(item => item.id === currentId.value) ?? root.value)
const selected = computed(() => items.value.find(item => item.id === selectedId.value))
const editable = computed(() => props.attempt.status === 'in_progress' && !props.busy && !props.pending)
const children = computed(() => items.value.filter(item => item.parent_id === current.value.id).sort((a, b) =>
  a.kind !== b.kind ? (a.kind === 'folder' ? -1 : 1) : a.name.localeCompare(b.name, 'fr')))
const shortcuts = computed(() => items.value.filter(item => item.kind === 'folder' && item.parent_id === root.value.id))
const breadcrumbs = computed(() => {
  const result: FileItem[] = []
  let item: FileItem | undefined = current.value
  const seen = new Set<string>()
  while (item && !seen.has(item.id)) {
    result.unshift(item); seen.add(item.id)
    item = items.value.find(parent => parent.id === item?.parent_id)
  }
  return result
})
const dialogTitle = computed(() => ({ folder: 'Nouveau dossier', file: 'Nouveau fichier', rename: 'Renommer', delete: 'Supprimer cet élément ?', emptyTrash: 'Vider la corbeille ?', properties: 'Propriétés' })[dialogMode.value])
function allowed(action: string) { return editable.value && props.attempt.scenario.allowed_actions.includes(action) }

const historyEnabled = computed(() =>
  props.attempt.scenario.allowed_actions.includes('history.undo')
)

const canUndo = computed(() =>
  allowed('history.undo') &&
  (props.attempt.checkpoint.undo_stack?.length ?? 0) > 0
)

const canRedo = computed(() =>
  allowed('history.redo') &&
  (props.attempt.checkpoint.redo_stack?.length ?? 0) > 0
)

async function undo() {
  if (!canUndo.value) return
  await props.perform('history.undo', {})
}

async function redo() {
  if (!canRedo.value) return
  await props.perform('history.redo', {})
}
function shortcutIcon(item: FileItem) {
  return ({ Bureau: 'desktop', Documents: 'file', Images: 'image', Téléchargements: 'download' } as Record<string, string>)[item.name] ?? 'folder'
}
function fileType(item: FileItem) {
  if (item.kind === 'folder') return 'Dossier'
  const extension = item.name.includes('.') ? item.name.split('.').pop()?.toUpperCase() : ''
  return extension || 'Fichier'
}
function goTrash() {
  if (!showTrash.value) return
  inTrash.value = true
  selectedId.value = null
  selectedTrashId.value = null
  context.value = null
}

function go(id: string) {
  inTrash.value = false
  selectedTrashId.value = null
  currentId.value = id; selectedId.value = null; context.value = null
  try { sessionStorage.setItem(`officelab-folder-${props.attempt.id}`, id) } catch { /* optional preference */ }
}
function open(item: FileItem) {
  if (item.kind === 'folder') go(item.id)
  else { selectedId.value = item.id; showDialog('properties') }
}
function select(item: FileItem) { selectedId.value = item.id; context.value = null }
function showDialog(mode: typeof dialogMode.value) {
  const action = ({ folder: 'folder.created', file: 'file.created', rename: 'item.renamed', delete: deleteAction.value, emptyTrash: 'trash.emptied' } as Record<string, string>)[mode]
  if (action && !allowed(action)) return
  if (['rename', 'delete', 'properties'].includes(mode) && !selected.value) return
  if (mode === 'emptyTrash' && (!inTrash.value || !trashEntries.value.length)) return
  returnFocus = document.activeElement instanceof HTMLElement ? document.activeElement : null
  dialogMode.value = mode; dialogItem.value = selected.value ?? null
  name.value = mode === 'rename' ? selected.value!.name : ''
  context.value = null
  dialog.value?.showModal()
  nextTick(() => { input.value?.focus(); input.value?.select() })
}
function closeDialog() {
  if (props.busy) return
  dialog.value?.close()
  if (returnFocus?.isConnected) returnFocus.focus()
  else fileArea.value?.focus()
}
async function submitDialog() {
  const item = dialogItem.value
  let type: string, payload: Record<string, string>
  if (dialogMode.value === 'emptyTrash') {
    type = 'trash.emptied'; payload = {}
  }
  else if (dialogMode.value === 'delete') {
    type = deleteAction.value; payload = { item_id: item!.id } }
  else if (dialogMode.value === 'rename') { type = 'item.renamed'; payload = { item_id: item!.id, name: name.value.trim() } }
  else { type = dialogMode.value === 'folder' ? 'folder.created' : 'file.created'; payload = { item_id: newEventId(), parent_id: current.value.id, name: name.value.trim() } }
  if (await props.perform(type, payload)) closeDialog()
}
async function retryDialog() {
  if (await props.retry()) closeDialog()
}

async function restoreSelected() {
  if (!selectedTrash.value || !allowed('item.restored')) return

  const ok = await props.perform(
    'item.restored',
    { item_id: selectedTrash.value.id }
  )

  if (ok) selectedTrashId.value = null
}
function cut() {
  if (selected.value && allowed('item.moved')) {
    cutId.value = selected.value.id
    copiedId.value = null
    context.value = null
  }
}

function copy() {
  if (selected.value && allowed('item.copied')) {
    copiedId.value = selected.value.id
    cutId.value = null
    context.value = null
  }
}

const canPaste = computed(() =>
  (cutId.value !== null && allowed('item.moved')) ||
  (copiedId.value !== null && allowed('item.copied'))
)
async function move(id: string, parent: string) {
  if (!allowed('item.moved')) return
  if (await props.perform('item.moved', { item_id: id, parent_id: parent })) {
    selectedId.value = null; if (cutId.value === id) cutId.value = null
  }
}
async function paste() {
  if (!canPaste.value) return

  if (cutId.value) {
    await move(cutId.value, current.value.id)
  } else if (copiedId.value) {
    const ok = await props.perform('item.copied', {
      item_id: copiedId.value,
      parent_id: current.value.id,
      new_item_id: newEventId(),
    })

    if (ok) selectedId.value = null
  }

  context.value = null
}
function startDrag(event: DragEvent, item: FileItem) {
  if (!allowed('item.moved')) { event.preventDefault(); return }
  dragId.value = item.id
  if (event.dataTransfer) { event.dataTransfer.effectAllowed = 'move'; event.dataTransfer.setData('text/plain', item.id) }
}
function dragOver(event: DragEvent, parent: string) {
  if (!dragId.value || !allowed('item.moved') || dragId.value === parent) return
  event.preventDefault(); dropId.value = parent
  if (event.dataTransfer) event.dataTransfer.dropEffect = 'move'
}
function drop(event: DragEvent, parent: string) {
  event.preventDefault(); const id = dragId.value; dragId.value = null; dropId.value = null
  if (id) void move(id, parent)
}
function showContext(event: MouseEvent, item?: FileItem) {
  if (props.busy) return
  selectedId.value = item?.id ?? null
  const box = (event.currentTarget as HTMLElement).getBoundingClientRect()
  context.value = { x: Math.max(8, Math.min(event.clientX || box.left + 15, window.innerWidth - 225)), y: Math.max(8, Math.min(event.clientY || box.top + 20, window.innerHeight - 330)) }
  nextTick(() => menu.value?.querySelector<HTMLButtonElement>('button:not(:disabled)')?.focus())
}
function menuKeys(event: KeyboardEvent) {
  const buttons = Array.from(menu.value?.querySelectorAll<HTMLButtonElement>('button:not(:disabled)') ?? [])
  if (event.key === 'Escape') { context.value = null; fileArea.value?.focus(); event.stopPropagation() }
  if (['ArrowDown', 'ArrowUp', 'Home', 'End'].includes(event.key)) {
    event.preventDefault()
    const index = buttons.indexOf(document.activeElement as HTMLButtonElement)
    buttons[event.key === 'Home' ? 0 : event.key === 'End' ? buttons.length - 1 : (index + (event.key === 'ArrowUp' ? -1 : 1) + buttons.length) % buttons.length]?.focus()
  }
}
function keys(event: KeyboardEvent) {
  if ((event.target as HTMLElement).closest('input, textarea, select, dialog')) return

  const modifier = event.ctrlKey || event.metaKey
  const key = event.key.toLowerCase()

  if (modifier && !event.altKey && key === 'z') {
    if (event.shiftKey) {
      if (canRedo.value) {
        event.preventDefault()
        void redo()
      }
    } else if (canUndo.value) {
      event.preventDefault()
      void undo()
    }
    return
  }

  if (modifier && !event.altKey && key === 'y') {
    if (canRedo.value) {
      event.preventDefault()
      void redo()
    }
    return
  }

  if (inTrash.value) {
    if (event.key === 'Escape') selectedTrashId.value = null
    return
  }
  if (event.key === 'F2') { event.preventDefault(); showDialog('rename') }
  if (event.key === 'Delete') { event.preventDefault(); showDialog('delete') }
  if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 'x') { event.preventDefault(); cut() }
  if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 'c') { event.preventDefault(); copy() }
  if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 'v') { event.preventDefault(); void paste() }
  if (event.key === 'Escape') { context.value = null; cutId.value = null; copiedId.value = null }
}
function outside(event: PointerEvent) { if (!(event.target as HTMLElement).closest('.context-menu')) context.value = null }
watch(items, () => {
  if (!items.value.some(item => item.id === selectedId.value)) selectedId.value = null
  if (!items.value.some(item => item.id === cutId.value)) cutId.value = null
  if (!items.value.some(item => item.id === copiedId.value)) copiedId.value = null
  if (!items.value.some(item => item.id === currentId.value)) go(root.value.id)
})
watch(trashEntries, () => {
  if (!trashEntries.value.some(entry => entry.id === selectedTrashId.value)) {
    selectedTrashId.value = null
  }
})

onMounted(() => {
  try {
    const saved = sessionStorage.getItem(`officelab-folder-${props.attempt.id}`)
    if (items.value.some(item => item.id === saved && item.kind === 'folder')) currentId.value = saved!
  } catch { /* optional preference */ }
  document.addEventListener('pointerdown', outside)
})
onUnmounted(() => document.removeEventListener('pointerdown', outside))
</script>

<template>
  <section class="explorer" aria-label="Explorateur de fichiers" @keydown="keys">
    <div class="window-titlebar"><span class="window-mark"><LabIcon name="folder" :size="19" /></span><strong>Mes fichiers</strong><span class="window-detail">Espace d’entraînement</span></div>
    <div v-if="inTrash" class="toolbar" aria-label="Actions sur la corbeille">
      <template v-if="historyEnabled">
        <button :disabled="!canUndo"
                title="Annuler (Ctrl+Z)"
                @click="undo">
          <span aria-hidden="true">↶</span>
          <span>Annuler</span>
        </button>

        <button :disabled="!canRedo"
                title="Rétablir (Ctrl+Y)"
                @click="redo">
          <span aria-hidden="true">↷</span>
          <span>Rétablir</span>
        </button>

        <span class="toolbar-divider"></span>
      </template>
      <button :disabled="!selectedTrash || !allowed('item.restored')"
              @click="restoreSelected">
        <LabIcon name="reset" />
        <span>Restaurer</span>
      </button>
      <button :disabled="!trashEntries.length || !allowed('trash.emptied')"
              @click="showDialog('emptyTrash')">
        <LabIcon name="trash" />
        <span>Vider la corbeille</span>
      </button>
    </div>
    <div v-else class="toolbar" aria-label="Actions sur les fichiers">
      <template v-if="historyEnabled">
        <button :disabled="!canUndo"
                title="Annuler (Ctrl+Z)"
                @click="undo">
          <span aria-hidden="true">↶</span>
          <span>Annuler</span>
        </button>

        <button :disabled="!canRedo"
                title="Rétablir (Ctrl+Y)"
                @click="redo">
          <span aria-hidden="true">↷</span>
          <span>Rétablir</span>
        </button>

        <span class="toolbar-divider"></span>
      </template>
      <button :disabled="!allowed('folder.created')" @click="showDialog('folder')"><LabIcon name="folder" />Nouveau dossier</button>
      <button :disabled="!allowed('file.created')" @click="showDialog('file')"><LabIcon name="plus" />Nouveau fichier</button>
      <span class="toolbar-divider"></span>
      <button :disabled="!selected || !allowed('item.renamed')" title="Renommer (F2)" @click="showDialog('rename')"><LabIcon name="rename" /><span>Renommer</span></button>
      <button :disabled="!selected || !allowed('item.moved')" title="Couper (Ctrl+X)" @click="cut"><LabIcon name="cut" /><span>Couper</span></button>
      <button :disabled="!selected || !allowed('item.copied')" title="Copier (Ctrl+C)" @click="copy"><LabIcon name="copy" /><span>Copier</span></button>
      <button :disabled="!canPaste" title="Coller (Ctrl+V)" @click="paste"><LabIcon name="paste" /><span>Coller</span></button>
      <button :disabled="!selected || !allowed(deleteAction)" title="Supprimer (Suppr)" @click="showDialog('delete')"><LabIcon name="trash" /><span>Supprimer</span></button>
      <button class="icon-button" :disabled="!selected" aria-label="Propriétés" title="Propriétés" @click="showDialog('properties')"><LabIcon name="info" /></button>
    </div>
    <div class="explorer-layout">
      <nav class="folder-sidebar" aria-label="Accès rapide">
        <p class="section-label">ACCÈS RAPIDE</p>
        <button v-for="folder in shortcuts" :key="folder.id" :class="{ active: !inTrash && current.id === folder.id, 'drop-target': dropId === folder.id }" :aria-current="current.id === folder.id ? 'location' : undefined" :data-folder-id="folder.id" @click="go(folder.id)" @dragover="dragOver($event, folder.id)" @dragleave="dropId = null" @drop="drop($event, folder.id)"><LabIcon :name="shortcutIcon(folder)" />{{ folder.name }}</button>
        <p class="section-label sidebar-second">MON ESPACE</p>
        <button :class="{ active: !inTrash && current.id === root.id, 'drop-target': dropId === root.id }" @click="go(root.id)" @dragover="dragOver($event, root.id)" @dragleave="dropId = null" @drop="drop($event, root.id)"><LabIcon name="home" />Tous les dossiers</button>
        <button v-if="showTrash"
                :class="{ active: inTrash }"
                :aria-current="inTrash ? 'location' : undefined"
                @click="goTrash">
          <LabIcon name="trash" />
          Corbeille
          <span v-if="trashEntries.length">({{ trashEntries.length }})</span>
        </button>
        <div class="sidebar-tip"><LabIcon name="info" :size="18" /><p>Tout se passe ici.<br>Vos vrais fichiers ne sont pas modifiés.</p></div>
      </nav>
      <div class="folder-content">
        <template v-if="inTrash">
          <div class="navigation-bar">
            <nav class="breadcrumbs" aria-label="Emplacement">
              <LabIcon name="trash" :size="18" />
              <strong>Corbeille</strong>
            </nav>
          </div>

          <div class="file-area list" tabindex="0"
               aria-label="Éléments supprimés">

            <button v-for="entry in trashEntries"
                    :key="entry.id"
                    class="file-item"
                    :class="{ selected: selectedTrashId === entry.id }"
                    :aria-pressed="selectedTrashId === entry.id"
                    @click="selectedTrashId = entry.id">

              <span class="item-art">
                <LabIcon
                  :name="entry.item.kind === 'folder' ? 'folder' : 'file'"
                  :size="30"
                />
              </span>

              <span class="item-name">{{ entry.item.name }}</span>

              <span class="item-type">
                {{ entry.item.kind === 'folder' ? 'Dossier' : 'Fichier' }}
                · {{ entry.count }} élément(s)
                · Origine :
                {{ items.find(item => item.id === entry.originalParentId)?.name
                   ?? 'Dossier absent' }}
              </span>
            </button>

            <div v-if="!trashEntries.length" class="empty-folder">
              <LabIcon name="trash" :size="46" />
              <h3>La corbeille est vide</h3>
              <p>Les éléments supprimés apparaîtront ici.</p>
            </div>
          </div>

          <div class="explorer-status" role="status">
            <span>{{ trashEntries.length }} élément(s) dans la corbeille</span>
            <span>Sélectionnez un élément pour le restaurer.</span>
          </div>
        </template>

        <template v-else>
        <div class="navigation-bar">
          <button class="icon-button" :disabled="!current.parent_id" aria-label="Dossier parent" title="Dossier parent" @click="go(current.parent_id!)"><LabIcon name="up" /></button>
          <nav class="breadcrumbs" aria-label="Chemin du dossier"><template v-for="(folder, index) in breadcrumbs" :key="folder.id"><LabIcon v-if="index" name="arrow" :size="13" /><button :aria-current="folder.id === current.id ? 'location' : undefined" @click="go(folder.id)">{{ folder.name }}</button></template></nav>
          <div class="view-switch" aria-label="Affichage"><button :class="{ active: view === 'grid' }" :aria-pressed="view === 'grid'" aria-label="Vignettes" title="Vignettes" @click="view = 'grid'"><LabIcon name="grid" :size="18" /></button><button :class="{ active: view === 'list' }" :aria-pressed="view === 'list'" aria-label="Liste" title="Liste" @click="view = 'list'"><LabIcon name="list" :size="18" /></button></div>
        </div>
        <div v-if="view === 'list'" class="list-heading"><span>Nom</span><span>Type</span></div>
        <div ref="fileArea" class="file-area" :class="[view, { 'drop-target': dropId === current.id }]" tabindex="0" :aria-label="`Contenu de ${current.name}`" @click.self="selectedId = null" @contextmenu.prevent="showContext($event)" @dragover.self="dragOver($event, current.id)" @drop.self="drop($event, current.id)">
          <button v-for="item in children" :key="item.id" class="file-item" :class="{ selected: selectedId === item.id, cut: cutId === item.id, 'drop-target': dropId === item.id }" :aria-pressed="selectedId === item.id" :data-item-id="item.id" :draggable="allowed('item.moved')" @click.stop="select(item)" @dblclick="open(item)" @keydown.enter.prevent="open(item)" @contextmenu.prevent.stop="showContext($event, item)" @dragstart="startDrag($event, item)" @dragend="dragId = null; dropId = null" @dragover="item.kind === 'folder' && dragOver($event, item.id)" @dragleave="dropId = null" @drop.stop="item.kind === 'folder' && drop($event, item.id)">
            <span class="item-art" :class="item.kind === 'folder' ? 'folder-art' : 'document-art'">
              <template v-if="item.kind === 'folder'"><span class="folder-back"></span><span class="folder-front"></span></template>
              <template v-else><LabIcon :name="['JPG', 'PNG'].includes(fileType(item)) ? 'image' : 'file'" :size="32" /><span class="extension" :class="{ picture: ['JPG', 'PNG'].includes(fileType(item)) }">{{ fileType(item).slice(0, 5) }}</span></template>
            </span>
            <span class="item-name">{{ item.name }}</span><span class="item-type">{{ item.kind === 'folder' ? 'Dossier' : `Fichier ${fileType(item)}` }}</span>
          </button>
          <div v-if="!children.length" class="empty-folder"><LabIcon name="folder" :size="48" /><h3>Ce dossier est vide</h3><p>Créez un dossier ou collez un élément pour commencer.</p></div>
        </div>
        <div class="explorer-status" role="status"><span>{{ children.length }} élément(s)<span v-if="selected"> · {{ selected.name }}</span></span><span v-if="cutId">Élément coupé · choisissez un dossier puis Coller</span><span v-else-if="copiedId">Élément copié · choisissez un dossier puis Coller</span><span v-else>Double-cliquez pour ouvrir</span></div>
        </template>
      </div>
    </div>
    <div v-if="context" ref="menu" class="context-menu" role="menu" aria-label="Actions" :style="{ left: `${context.x}px`, top: `${context.y}px` }" @keydown="menuKeys">
      <button v-if="selected?.kind === 'folder'" role="menuitem" @click="open(selected!)">Ouvrir</button>
      <button role="menuitem" :disabled="!allowed('folder.created')" @click="showDialog('folder')">Nouveau dossier</button>
      <button role="menuitem" :disabled="!allowed('file.created')" @click="showDialog('file')">Nouveau fichier</button>
      <button v-if="selected" role="menuitem" :disabled="!allowed('item.renamed')" @click="showDialog('rename')">Renommer <kbd>F2</kbd></button>
      <button v-if="selected" role="menuitem" :disabled="!allowed('item.moved')" @click="cut">Couper <kbd>Ctrl X</kbd></button>
      <button v-if="selected" role="menuitem" :disabled="!allowed('item.copied')" @click="copy">Copier <kbd>Ctrl C</kbd></button>
      <button role="menuitem" :disabled="!canPaste" @click="paste">Coller <kbd>Ctrl V</kbd></button>
      <button v-if="selected" role="menuitem" :disabled="!allowed(deleteAction)" @click="showDialog('delete')">Supprimer</button>
      <button v-if="selected" role="menuitem" @click="showDialog('properties')">Propriétés</button>
    </div>
    <dialog ref="dialog" class="action-dialog" aria-labelledby="dialog-title" @cancel.prevent="closeDialog">
      <form @submit.prevent="submitDialog">
        <div class="dialog-heading"><h2 id="dialog-title">{{ dialogTitle }}</h2><button type="button" class="icon-button" aria-label="Fermer" :disabled="busy" @click="closeDialog"><LabIcon name="close" /></button></div>
        <template v-if="['folder', 'file', 'rename'].includes(dialogMode)"><p>Dans {{ current.name }}<span v-if="dialogMode === 'rename'"> · {{ dialogItem?.name }}</span></p><label for="item-name">{{ dialogMode === 'rename' ? 'Nouveau nom' : 'Nom' }}</label><input id="item-name" ref="input" v-model="name" required maxlength="255" autocomplete="off" :disabled="busy" :placeholder="dialogMode === 'folder' ? 'Nom du dossier' : 'exemple.txt'" /></template>
        <p v-else-if="dialogMode === 'delete'">
          {{ deleteAction === 'item.trashed' ? 'Placer' : 'Supprimer définitivement' }}
          « {{ dialogItem?.name }} »
          {{ deleteAction === 'item.trashed'
             ? 'dans la corbeille ?'
             : 'de cet exercice ? Un dossier doit être vide.' }}
        </p>
        <p v-else-if="dialogMode === 'emptyTrash'">
          Supprimer définitivement les {{ trashEntries.length }}
          élément(s) de la corbeille ?
          {{ historyEnabled
             ? 'Cette action peut être annulée tant que l’historique est disponible.'
             : 'Cette action est irréversible.' }}
        </p>
        <dl v-else><dt>Nom</dt><dd>{{ dialogItem?.name }}</dd><dt>Type</dt><dd>{{ dialogItem ? fileType(dialogItem) : '' }}</dd><dt>Emplacement</dt><dd>{{ breadcrumbs.map(folder => folder.name).join(' / ') }}</dd></dl>
        <p v-if="error" class="dialog-error" role="alert">{{ error }}</p><div class="dialog-actions"><button type="button" class="secondary-button" :disabled="busy" @click="closeDialog">{{ dialogMode === 'properties' ? 'Fermer' : 'Annuler' }}</button><button v-if="pending" type="button" class="primary-button" :disabled="busy" @click="retryDialog">Réessayer l’action</button><button v-else-if="dialogMode !== 'properties'" class="primary-button" :disabled="busy || (['folder', 'file', 'rename'].includes(dialogMode) && !name.trim())">{{ dialogMode === 'emptyTrash' ? 'Vider définitivement' : dialogMode === 'delete' ? 'Supprimer' : dialogMode === 'rename' ? 'Renommer' : 'Créer' }}</button></div>
      </form>
    </dialog>
  </section>
</template>
