# Select the sounds and transcriptions of those sounds to use in the experiment.

library(magrittr)
library(dplyr)
library(ggplot2)
library(broom)
library(lme4)

library(wordsintransition)
data("transcription_matches")

scale_x_message_label <- scale_x_discrete("")
base_theme <- theme_minimal() +
  theme(axis.ticks = element_blank())

set.seed(533)

# Start with the transcriptions that were used
# in the transcription matches experiment

transcription_matches %<>%
  recode_question_type %>%
  recode_message_type %>%
  recode_version %>%
  label_outliers %>%
  filter(is_outlier == 0, question_type != "catch_trial") %>%
  mutate(word_char_n = nchar(word))

ggplot(transcription_matches, aes(x = message_label, y = is_correct)) +
  geom_point(aes(group = word), stat = "summary", fun.y = "mean",
             position = position_jitter(width = 0.1)) +
  scale_x_message_label +
  labs(title = "Transcriptions by message type") +
  base_theme

# Drop transcriptions for messages where match to seed accuracy was not
# significantly better than chance.

alpha <- 0.01
word_labels <- transcription_matches %>%
  mutate(chance = 0.25) %>%
  group_by(word) %>%
  do(mod = glm(is_correct ~ offset(chance), data = .)) %>%
  tidy(mod) %>%
  mutate(is_better_than_chance = (estimate > 0) & (p.value < alpha)) %>%
  select(word, is_better_than_chance)

transcription_matches %<>% left_join(word_labels)

word_means <- transcription_matches %>%
  group_by(message_type, seed_id, word, word_char_n, word_category, is_better_than_chance) %>%
  summarize(is_correct = mean(is_correct, na.rm = TRUE)) %>%
  ungroup %>%
  recode_message_type

ggplot(word_means, aes(x = message_label, y = is_correct)) +
  geom_point(aes(color = is_better_than_chance),
             position = position_jitterdodge(jitter.width = 0.2, dodge.width = 0.5)) +
  geom_hline(yintercept = 0.25, lty = 2) +
  scale_x_message_label +
  scale_color_discrete(paste("p <", alpha), labels = c("False", "True")) +
  labs(title = "Transcriptions with match accuracies > chance") +
  base_theme +
  theme(legend.position = "bottom")

above_chance <- word_means %>% filter(is_better_than_chance == 1)

# Calculate desired mean and sd based on transcriptions of
# last gen imitations (the lowest performing group).
baseline_group <- filter(above_chance, message_type == "last_gen_imitation")
desired_mean <- mean(baseline_group$is_correct, na.rm = TRUE)

error_prop <- 0.1
min_mean <- desired_mean - desired_mean * error_prop
max_mean <- desired_mean + desired_mean * error_prop

check_within_desired_range <- function(sample) {
  sample_mean <- mean(sample$is_correct, na.rm = TRUE)
  valid_mean <- (sample_mean > min_mean) & (sample_mean < max_mean)
  valid_mean
}

# Select transcriptions evenly distributed among
# message types and categories and controlling
# for overall match to seed accuracy.

n_words_per_message <- 3
n_word_categories <- 4
max_iterations <- 10000
max_word_length <- 8

smart_sample <- function(frame) {
  for (i in 1:max_iterations) {
    sample <- sample_n(frame, size = n_words_per_message * n_word_categories)
    if (check_within_desired_range(sample)) {
      print('Found a sample that works!')
      return(sample)
    }
  }
  print('Unable to find a sample satisfying the desired criteria, returning a random sample')
  sample_n(frame, size = n_words_per_message)
}

sampled_labels <- above_chance %>%
  filter(is_correct < 0.8, word_char_n <= max_word_length) %>%
  group_by(message_type) %>%
  do({ smart_sample(.) }) %>%
  ungroup %>%
  mutate(is_selected = TRUE) %>%
  select(word, is_selected)

selected <- above_chance %>%
  left_join(sampled_labels)

ggplot(selected, aes(x = message_label, y = is_correct)) +
  geom_point(aes(color = is_selected), position = position_jitterdodge(jitter.width = 0.2, dodge.width = 0.5),
             shape = 1) +
  geom_hline(aes(yintercept = is_correct), data = data.frame(is_correct = c(min_mean, max_mean)),
             lty = 2) +
  coord_cartesian(ylim = c(0, 1)) +
  scale_x_message_label +
  base_theme +
  theme(legend.position = "bottom")

final <- selected %>%
  rename(category = word_category) %>%
  select(message_type, seed_id, category, word) %>%
  unique

write.csv(final, "stimuli/messages.csv", row.names = FALSE)
