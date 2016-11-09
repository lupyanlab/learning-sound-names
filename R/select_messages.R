# Select the sounds and transcriptions of those sounds to use in the experiment.

library(magrittr)
library(dplyr)
library(ggplot2)
library(broom)
library(lme4)

library(wordsintransition)
data("transcription_matches")

# Start with transcriptions that were used
# in the transcription matches experiment

transcription_matches %<>%
  recode_question_type %>%
  recode_message_type %>%
  recode_version %>%
  label_outliers %>%
  filter(is_outlier == 0, question_type != "catch_trial")

ggplot(transcription_matches, aes(x = message_label, y = is_correct)) +
  geom_point(aes(group = word), stat = "summary", fun.y = "mean",
             position = position_jitter(width = 0.1))

# Drop transcriptions for messages that were not significantly
# better than chance.
alpha <- 0.001
word_labels <- transcription_matches %>%
  mutate(chance = 0.25) %>%
  group_by(word) %>%
  do(mod = glm(is_correct ~ offset(chance), data = .)) %>%
  tidy(mod) %>%
  mutate(is_better_than_chance = (estimate > 0) & (p.value < alpha)) %>%
  select(word, is_better_than_chance)

transcription_matches %<>% left_join(word_labels)

word_means <- transcription_matches %>%
  group_by(message_label, word, is_better_than_chance) %>%
  summarize(is_correct = mean(is_correct, na.rm = TRUE))

ggplot(word_means, aes(x = message_label, y = is_correct)) +
  geom_point(aes(color = is_better_than_chance),
             position = position_jitterdodge(jitter.width = 0.1, dodge.width = 0.5))

selected <- transcription_matches %>%
  filter(is_better_than_chance == 1) %>%
  rename(category = word_category) %>%
  select(seed_id, category, word) %>%
  unique

write.csv(selected, "stimuli/messages.csv", row.names = FALSE)
