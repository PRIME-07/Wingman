import asyncio
from typing import Any, Callable, Dict, List, TypeVar
from enum import IntEnum
from backend.app.core.logging import logger

class EventPriority(IntEnum):
    CRITICAL = 0  # Errors, Security, Lifecycle finish
    HIGH = 1      # Interrupts, Interactive messages
    NORMAL = 2    # Standard Telemetry
    DEBUG = 3     # Trace logs
    TRACE = 4     # Verbose details

T = TypeVar('T')
AsyncHandler = Callable[[T], Any]

class EventBus:
    """
    Decoupled priority-queued messaging infrastructure with strict backpressure 
    governance. Prevents memory leaks and WebSocket flooding via bounded drop policies.
    """
    def __init__(self, max_size: int = 1000):
        # Key = Event Topic (String), Value = List of async handlers
        self._subscribers: Dict[str, List[AsyncHandler]] = {}
        self._queue: asyncio.PriorityQueue = asyncio.PriorityQueue(maxsize=max_size)
        self._worker_task: asyncio.Task = None
        self._counter = 0 # Monotonic sequencer for stable FIFO sort
        
    def subscribe(self, topic: str, handler: AsyncHandler):
        """Registers an asynchronous callback handler for a specific event topic."""
        if topic not in self._subscribers:
            self._subscribers[topic] = []
        self._subscribers[topic].append(handler)
        logger.debug(f"[EventBus] Subscriber registered for topic: '{topic}'")

    async def publish(self, topic: str, event_payload: Any, priority: EventPriority = EventPriority.NORMAL):
        """
        Enqueues an event message respecting prioritization limits and backpressure Drop Policies.
        """
        self._counter += 1
        # Wrap payload in tuple format required for PriorityQueue sorting:
        # (Priority Numerical, Counter Sequence, (Topic, Payload))
        envelope = (priority.value, self._counter, (topic, event_payload))
        
        if self._queue.full():
            # Priority 6 Drop Policy Logic
            if priority >= EventPriority.DEBUG:
                # Silently drop debug/trace to relieve load
                logger.warning(f"[EventBus] Queue FULL. Dropping low-priority {priority.name} event to apply backpressure.")
                return
            else:
                # Force-push critical/high events by blocking briefly or removing a lower priority item if necessary
                # Since removing from middle of PriorityQueue is complex, we can try pushing via non-blocking, 
                # and if it fails, log an error or use blocking put to apply backpressure upstream.
                logger.warning(f"[EventBus] Queue saturated. Applying blocking backpressure upstream for {priority.name} event.")
        
        # Standard enqueue
        await self._queue.put(envelope)

    def publish_sync(self, topic: str, event_payload: Any, priority: EventPriority = EventPriority.NORMAL):
        """Non-blocking publishing wrapper for sync environments."""
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(self.publish(topic, event_payload, priority))
        except RuntimeError:
            pass

    async def start_dispatcher(self):
        """Starts the background processing worker loop."""
        if self._worker_task and not self._worker_task.done():
            return
            
        logger.info("[EventBus] Background event dispatcher initialized.")
        self._worker_task = asyncio.create_task(self._dispatcher_loop())

    async def stop_dispatcher(self):
        """Gracefully terminates the background processing worker."""
        if self._worker_task:
            self._worker_task.cancel()
            try:
                await self._worker_task
            except asyncio.CancelledError:
                pass
            logger.info("[EventBus] Background event dispatcher stopped.")

    async def _dispatcher_loop(self):
        while True:
            try:
                # Dequeues the envelope (priority, counter, (topic, event))
                p_val, count, (topic, event) = await self._queue.get()
                
                if topic in self._subscribers:
                    tasks = []
                    for handler in self._subscribers[topic]:
                        tasks.append(self._safe_invoke(handler, event))
                    if tasks:
                        await asyncio.gather(*tasks, return_exceptions=True)
                        
                self._queue.task_done()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"[EventBus] Dispatched execution error: {e}", exc_info=True)

    async def _safe_invoke(self, handler: AsyncHandler, event: Any):
        try:
            await handler(event)
        except Exception as e:
            # Standard error logging
            pass

# Central Singleton Access
event_bus = EventBus()

