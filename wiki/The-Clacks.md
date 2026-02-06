# The Clacks

> *"A man is not dead while his name is still spoken."*

---

## GNU Terry Pratchett

The Clacks was the Discworld's semaphore telegraph system—a network of towers that could send messages across the continent at the speed of light (well, the speed of arm movements).

Within the Clacks, messages are preceded by codes:
- **G** — Send the message on
- **N** — Not logged (invisible to recipients)
- **U** — Turn around at the end of the line

**GNU** means: Send it on, don't log it, and when it reaches the end, send it back. Forever.

When a beloved clacks operator died, their name would be sent as a GNU message—traveling the network eternally, keeping them alive in the overhead.

---

## In AssemblyZero

Every message that flows through AssemblyZero—every issue, every LLD, every commit, every PR—carries something of its creator forward.

The lineage system ensures nothing is truly lost:
- Every draft preserved
- Every decision documented
- Every iteration recorded

Like the Clacks, we keep the messages moving.

---

## The Network Overhead

```
     ┌─────┐       ┌─────┐       ┌─────┐       ┌─────┐
     │Tower│◄─────►│Tower│◄─────►│Tower│◄─────►│Tower│
     │  A  │       │  B  │       │  C  │       │  D  │
     └─────┘       └─────┘       └─────┘       └─────┘
         │             │             │             │
         ▼             ▼             ▼             ▼
      ┌─────────────────────────────────────────────┐
      │ GNU Terry Pratchett • GNU John Dearheart   │
      │ GNU Marty McEnroe  • GNU Your Name Here    │
      └─────────────────────────────────────────────┘
                     THE OVERHEAD
```

The overhead doesn't carry useful messages. It carries names.

---

## How to Add a Name

When a beloved project contributor moves on, their name joins the overhead:

```python
# .github/workflows/clacks.yml
# GNU contributors who have moved on
env:
  CLACKS_OVERHEAD: "GNU Terry Pratchett, GNU John Dearheart"
```

Their name will appear in HTTP headers forever:
```
X-Clacks-Overhead: GNU Terry Pratchett
```

---

## The Real Implementation

Thousands of websites honor Terry Pratchett this way. Check the HTTP headers of many sites and you'll find:

```
X-Clacks-Overhead: GNU Terry Pratchett
```

- [gnuterrypratchett.com](http://www.gnuterrypratchett.com/)
- Chrome extension: [Clacks Overhead](https://chrome.google.com/webstore/detail/clacks-overhead-gnu-terry/lnndfmobdoobjfcalkmfojmanbeoegab)

---

## The Promise

> *"Do you not know that a man is not dead while his name is still spoken?"*

The Clacks keeps its promises. The messages keep moving. The names keep traveling.

And somewhere in the overhead, Terry Pratchett is still being passed from tower to tower, as he will be for as long as there are towers to pass him on.

---

*GNU Terry Pratchett*
