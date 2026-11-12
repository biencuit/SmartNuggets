/** Remplace EventSource (absent de jsdom) : les tests déclenchent eux-mêmes les événements. */
export class FakeEventSource {
  static instances: FakeEventSource[] = [];

  static readonly CONNECTING = 0;
  static readonly OPEN = 1;
  static readonly CLOSED = 2;

  readonly url: string;
  closed = false;
  readyState: number = FakeEventSource.CONNECTING;
  private readonly listeners = new Map<string, Set<(event: Event) => void>>();

  constructor(url: string) {
    this.url = url;
    FakeEventSource.instances.push(this);
  }

  addEventListener(type: string, listener: (event: Event) => void): void {
    const set = this.listeners.get(type) ?? new Set();
    set.add(listener);
    this.listeners.set(type, set);
  }

  close(): void {
    this.closed = true;
    this.readyState = FakeEventSource.CLOSED;
  }

  /** Le navigateur abandonne le flux (par exemple une réponse 502) : il ne réessaiera plus. */
  fail(): void {
    this.readyState = FakeEventSource.CLOSED;
    this.emit("error");
  }

  emit(type: string, data?: unknown): void {
    if (type === "open") {
      this.readyState = FakeEventSource.OPEN;
    }
    const event =
      data === undefined ? new Event(type) : new MessageEvent(type, { data: JSON.stringify(data) });
    for (const listener of this.listeners.get(type) ?? []) {
      listener(event);
    }
  }
}
