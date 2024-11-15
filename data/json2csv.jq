#!/usr/bin/env -S jq -rf

# Note: This expects a list of objects as input

# Convert object values to strings
map(
  with_entries(
    .value = (
      .value
      |
      tostring
    )
  )
)

|

# Extract unique keys
(
  map(
    keys_unsorted
  )
  |
  add
  |
   unique
) as $keys

|

# Produce CSV output
(
  # First the keys
  (
    $keys|@csv
  )
  ,
  # Then the values
  (
    map(
      [
        .[$keys[]]
      ]
    )
    []
    |
    @csv
  )
)
