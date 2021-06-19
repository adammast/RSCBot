# RSCBot: sixMans

The `sixMans` cog allows members of the guild to queue to play in a Team vs Team series. The cog enables you to set up one or more queues in a guild. When a queue pops, it creates a text channel

## Installation

The `sixMans` cog has no other cog dependancies.

```
<p>cog install RSCBot sixMans
<p>load sixMans
```

<br>

# Setup

### Add a New Queue

The `<p>addNewQueue` command can be used to add a new queue.

```
<p>addNewQueue "<Queue Name>" <points for playing> <points for winning> <channel(s)>
```

### Set Category

The `<p>setCategory` can be used to set the category that contains the 6 mans text and voice channels.

```
<p>setCategory <cateory id>
```

### Set Helper Role

Sets the role that will be assigned to individuals to resolve issues with 6 mans queues and games.

```
<p>setHelperRole <role>
```

<br>

# Regular Use

#### `<p>q` - Queue for a 6 mans series

#### `<p>dq` - De-Queue from a 6 mans series

#### `<p>sr <winner>` - Report winner of a 6 mans series (Blue/Orange)

#### `<p>cg` - Cancel Game

<br>

# Helper Commands

#### `<p>cag` - "Check Active Games" - Lists all ongoing 6 mans series

#### `<p>getQueueNames` - Lists names of available queues

#### `<p>fr <winner>` - Forces result of 6 mans series (Blue/Orange)

#### `<p>fcg` - Force cancel game

#### `<p>kq <member>` - Kicks a member from a 6 mans queue
