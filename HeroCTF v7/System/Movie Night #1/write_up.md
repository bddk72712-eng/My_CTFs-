# Movie Night #1 – Writeup (tmux / "Alien" Challenge)

Flag: `Hero{1s_1t_tmux_0r_4l13n?_a20bac4b5aa32e8d9a8ccb75d228ca3e}`

---

## 1. First contact with the box

I logged in as `user` with the given password. No drama, no twist, just the standard ritual: `id`, `pwd`, `ls /home`, `cat /etc/passwd`.

I always start that way. People in CTFs have different aesthetics about tooling, but most of us share that basic routine. It is a small agreement inside the community: before chasing fantasies, confirm who you are and who lives next door.

What I saw:
- `user` exists, obviously.
- `dev` and `admin` exist.
- `/home/dev/flag.txt` exists and rejects `user`.

At this point the story is boring on purpose. The interesting part is the decision to stay boring for a few minutes instead of jumping into half-baked exploitation. That discipline matters more than any individual trick.

## 2. My bias toward complex systems

Once the basics were mapped, my attention went where my own history tends to drag it: infrastructure and policy.

So I did the usual:
- `sudo -l` to see whether someone made the classic mistake.
- `find / -perm -4000 -type f 2>/dev/null` to scan the usual landmines.

Nothing immediate for `dev` or `admin`. That already says something about whoever built this challenge: they are not relying on the default beginner escalations.

Then the configuration layer appeared:
- Under `/etc/dbus-1/`, there was a custom service: `com.system.ProcedureService`.
- `busctl list` and `busctl introspect` showed a full interface: `RegisterProcedure`, `ExecuteProcedure`, `ListProcedures`, `RemoveProcedure`, `GetStatus`.

Here my own bias kicked in. Whenever I see a custom service glued into the system bus, I assume that is the main axis of the challenge. That assumption is not neutral; it comes from years of seeing engineers over-engineer the control plane and forget trivial permissions.

So I tried the obvious misuse first: register something that calls `cat /home/dev/flag.txt` and execute it. The service answered with errors. No free lunch.

## 3. Reading code that does not want to be read

If I am forced to choose between guessing and reading source code, I will read the source. Every time.

The D-Bus configuration hinted that procedures were stored under `/var/procedures`. The service accepted base64 strings which it claimed were pickles. That combination is rarely gentle.

I generated malicious pickle payloads locally and used them to run commands as the `dbus-service` user when the service unpickled them. That angle gave me visibility into the code that actually defines the rules:

- `/opt/procservice/procedure-processing-service.py`
- `/opt/procservice/lib/utils.py`
- `/opt/procservice/lib/load_pickle.py`

Reading those files changed the picture:

- The main service runs as `root`, but it delegates unpickling to a helper script that runs as `dbus-service`.
- After unpickling, it checks the owner of the procedure file and executes the resulting code *as that owner*, never as root.
- `dbus-service` itself does not have access to `/home/dev/flag.txt`.
- A comment in the code explicitly mentions a TOCTOU issue. That is basically the author telling us: "this code will matter later".

For this first flag, the entire D-Bus stack functioned more as context and character development than as the actual mechanism of the crime. But walking through it was still useful. It exposed the mindset of the challenge author: comfortable with Python, D-Bus, privilege separation, and playful enough to leave a written note about the race condition.

## 4. /tmp, tmux, and the detail that actually moved the story

After the D-Bus detour, I went back to a simple habit that has saved people countless hours in real systems and in CTFs: look at `/tmp` and at the process list.

- `ls -la /tmp`
- `ps aux`

There it was:

- `/tmp/tmux-1002` with permissions `srw-rw-rw-`.
- Owned by `dev`.
- A `tmux -S /tmp/tmux-1002 ...` process running as `dev`.

Anyone who has ever debugged a long-lived tmux session recognizes this kind of setup. The important part here is not nostalgia, it is the access pattern: a tmux socket with read/write for everyone means any local user can feed keystrokes into `dev`'s shell.

The Alien quote from the statement — "Something has attached itself to him" — clicked at this point. It fits neatly with the idea of connecting into someone else’s live environment. No romanticism, just a very direct mapping between cinema dialogue and a very ordinary Unix construct.

## 5. Letting dev’s shell do the work

Once the tmux socket was identified as world-writable, the rest was straightforward and slightly anticlimactic in the best possible way.

Instead of trying to fully attach to the session, I used tmux as a remote keyboard for `dev`:

```bash
tmux -S /tmp/tmux-1002 send-keys 'cat /home/dev/flag.txt > /tmp/flag.txt; chmod 777 /tmp/flag.txt' Enter
```

This is the crucial point: the command is logically issued by `dev` inside the tmux-controlled shell. The system does not see `user` touching `/home/dev/flag.txt`; it sees `dev` reading their own file and writing to `/tmp/flag.txt`.

That separation matters. It is the entire privilege model expressed in a single line of shell.

## 6. Reading the flag and what stayed after the excitement

After that tmux line, finishing the challenge was almost mechanical:

```bash
cat /tmp/flag.txt
```

The output:

```text
Hero{1s_1t_tmux_0r_4l13n?_a20bac4b5aa32e8d9a8ccb75d228ca3e}
```

What interested me more than the string itself was the structure around it:

- A carefully built D-Bus and pickle setup that invites people to over-focus on serialization bugs and race conditions.
- A single misconfigured tmux socket in `/tmp` that quietly hands over the real power to anyone who respects basic local enumeration.
- A movie quote that does not just decorate the challenge, but directly encodes the intended thinking pattern: attach to the running thing that already has the access you want.

I read this kind of challenge as a gentle argument inside the wider security community: people talk a lot about exotic vulnerabilities, but many real escalations come from simple, human choices like giving a shared tmux socket too much trust.

I like that. It respects the reader. It assumes we can hold two layers in mind at once: the glamorous tooling and the quiet configuration mistake that actually changes who can read what.
