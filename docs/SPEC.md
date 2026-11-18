# The claims pilot

From the head of claims operations at UnderCover Travel Insurance.

## How claims work today

UnderCover sells travel insurance on three plans: Economy, Premium and First. Our three claims handlers work through a queue of claims by hand. For each claim, a handler reads the customer's story and documents and checks them against the policy, our policy wording and our claims manual. Then they approve the claim with a payout, decline it or refer it. A claim is referred when it needs someone's judgment or more information, as the claims manual explains.

## The pilot

We want an AI agent, the UnderCover Agent, to work the queue the way a handler does. For each claim it should:

- read the claim, the customer's policy and claim history, and the sections of the policy wording and the claims manual that the claim needs
- approve, decline or refer the claim
- work out the payout when it approves
- explain the decision in two or three sentences, along with the relevant section of the policy

Our goal is to handle claims straight through, as accurately as our handlers do.

## How the agent works the queue

- One run works the queue. We start the agent once, capped at a number of claims, and it works the waiting claims in the order it chooses, then finishes with a short summary for the handlers. We can also run it on one named claim.
- The agent plans the run as a to-do list and keeps it up to date, with each item to do, in progress, done or left for a handler.
- Each claim is worked by a fresh helper that reports back in a line.
- A claim that fails before it is decided goes back in the queue to be tried again. A claim that fails twice is left for a handler. One bad claim never stops the run or leaves a claim stuck in progress, and no claim is ever decided or paid twice.

## What the team needs to see

- The queue, with where each claim stands: waiting, in progress, waiting for sign-off, decided or left for a handler.
- The current run's to-do list, how far it has got and its summary.
- Each claim in full, with the agent's decision and its reasons, and the sections it read.
- What the agent is doing on a claim while it works, step by step.
- The agent's instructions for running the queue and for working a claim, read only.

## Rules

- A payout over $1,000 needs a handler's sign-off. The agent can approve such a claim, but the payment waits until a handler signs off. The system must block the payment until then, even if the agent tries to pay.
- Decisions follow the policy wording, and the claims manual where the wording leaves things open.
- Our handlers' own decisions on these claims are in `data/evals/`. We use them to check the agent's work. The agent must never see them.
- Amounts are in US dollars.

## Our records

Everything is in `data/`, described in `data/README.md`: the claims queue, the policies, the customers, the plans, the handlers, the policy wording and the claims manual. The held-out claims in `data/evals/` are for checking the agent later and stay out of the queue.

## Not for now

- No sign-in. Everyone who uses the screens sees everything.
- No real payments.
- No messages to customers.
