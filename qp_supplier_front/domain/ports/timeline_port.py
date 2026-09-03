# -*- coding: utf-8 -*-
"""
timeline_port.py (domain - ports)
==================================
Contrato del timeline de facturas documenteme: lectura del historial y
persistencia de entradas (comentarios, cambios de estado, creacion). La capa
de recursos (resources/documenteme/timeline.py) y los puntos de transicion de
estado dependen de ESTE contrato, no de Frappe ni del MemoryStore.

Cada operacion tiene dos implementaciones:
  - adaptador real: infrastructure/adapters/timeline_adapter.py
    (RealTimelineAdapter, sobre frappe ORM).
  - adaptador in-memory: simulation/timeline_memory.py
    (MemoryTimelineAdapter, sobre simulation/store.MemoryStore).

No hay clase abstracta por compatibilidad Python 3.6: las firmas documentadas
son la referencia del contrato y ambos adaptadores deben cubrirlas.

Metodos (doc_name = name del qp_SP_DocumentDetail):
    get(doc_name) -> [entry]
        Lista de entradas del timeline (filas qp_SP_TimelineEntry: creacion,
        cambio de estado y comentarios), ordenada DESC por fecha (mas reciente
        primero). No incluye los event_logs de documenteme (030/032/031/033).
        Formato de entry en uses_cases/documenteme/timeline.py (dict con
        type/message/old_state/new_state/entry_by/entry_date).

    add_comment(doc_name, comment, user=None, now=None) -> entry
        Agrega una entrada de tipo comentario y retorna la entrada creada.
        user es el nombre del usuario; si no se pasa, el adaptador real lo
        resuelve de la sesion y el de memoria usa "Administrator".

    set_state(doc_name, new_state, extra_fields=None, user=None, now=None,
              old_state=None) -> entry|None
        Aplica el cambio de estado (atomico) y registra la entrada "estado".
        extra_fields permite fijar campos adicionales en el mismo save (p. ej.
        {"qp_is_event_completed": 1}). old_state permite indicar el estado
        previo cuando el origen ya lo actualizo (re-sync); si no se pasa, el
        adaptador lo lee antes de escribir. Retorna None (no-op) si el estado
        no cambia.

    record_creation(doc_name, user=None, now=None) -> entry
        Registra la entrada de creacion del documento (primera sincronizacion).
        Normalmente se dispara desde el hook before_save del doctype.

    get_comments(doc_name) -> [entry]
        SOLO las entradas de tipo comentario (conversacion), ordenadas DESC
        por fecha. El modal de conversaciones consume este metodo; las
        entradas de creacion/estado viven en get() y se muestran en el modal
        de alertas.

    mark_read(doc_name, user=None, now=None) -> None
        Registra/actualiza la marca de lectura de un usuario en
        qp_SP_TimelineRead (child de qp_SP_DocumentDetail). Si el usuario ya
        tiene una fila, se actualiza su last_read; si no, se inserta.

    unread_count(doc_name, user=None) -> int
        Cantidad de comentarios NO leidos por el usuario: comentarios con
        entry_date posterior a su last_read y que NO fueron escritos por el
        propio usuario. Si el usuario no tiene last_read, todos los comentarios
        ajenos cuentan como no leidos.

    has_unread(doc_name, user=None) -> bool
        True si hay comentarios no leidos para el usuario.
"""