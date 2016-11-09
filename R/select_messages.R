# Select the sounds and transcriptions of those sounds to use in the experiment.

library(magrittr)
library(dplyr)
library(ggplot2)
library(broom)

library(wordsintransition)
data("transcription_matches")

transcription_matches %<>%
  recode_question_type %>%
  recode_message_type %>%
  recode_version %>%
  label_outliers %>%
  filter(is_outlier == 0, question_type != "catch_trial") %>%
  mutate(chance = 0.25)

ggplot(transcription_matches, aes(x = message_label, y = is_correct)) +
  geom_point(aes(group = word), stat = "summary", fun.y = "mean",
             position = position_jitter(width = 0.1))


# Drop transcriptions for messages that were not significantly
# better than chance.
alpha <- 0.001
message_labels <- transcription_matches %>%
  group_by(message_id) %>%
  do(mod = glm(is_correct ~ 1, data = ., offset = chance)) %>%
  tidy(mod) %>%
  ungroup %>%
  mutate(is_better_than_chance = (estimate > 0) & (p.value < alpha)) %>%
  select(message_id, is_better_than_chance)

transcription_matches %<>% left_join(message_labels)

message_means <- transcription_matches %>%
  group_by(message_label, word, is_better_than_chance) %>%
  summarize(is_correct = mean(is_correct, na.rm = TRUE))

ggplot(message_means, aes(x = message_label, y = is_correct)) +
  geom_point(aes(color = is_better_than_chance),
             position = position_jitterdodge(jitter.width = 0.1, dodge.width = 0.5))

selected <- transcription_matches %>%
  filter(is_better_than_chance == 1) %>%
  rename(category = word_category)

write.csv(selected, "stimuli/messages.csv", row.names = FALSE)
