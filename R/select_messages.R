# Select the sounds and transcriptions of those sounds to use in the experiment.

library(magrittr)
library(dplyr)
library(ggplot2)
library(broom)
library(lme4)
library(stringr)

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
  mutate(word_length = nchar(word))

ggplot(transcription_matches, aes(x = message_label, y = is_correct)) +
  geom_point(aes(group = word), stat = "summary", fun.y = "mean",
             position = position_jitter(width = 0.1)) +
  scale_x_message_label +
  labs(title = "Transcriptions by message type") +
  base_theme

# Drop transcriptions for messages where match to seed accuracy was not
# significantly better than chance.

alpha <- 0.01
performace_labels <- transcription_matches %>%
  mutate(chance = 0.25) %>%
  group_by(word) %>%
  do(mod = glm(is_correct ~ offset(chance), data = .)) %>%
  tidy(mod) %>%
  mutate(is_better_than_chance = (estimate > 0) & (p.value < alpha)) %>%
  select(word, is_better_than_chance)

# Summarize performance by word, merging in the performance labels,
# and creating new variables for filtering based on word length and
# unique character count.

unique_char <- function(x) {
  # unique_char("d-d-d") == 1
  # unique_char("da da da") == 2
  x %>%
    str_replace_all("[[:punct:][:blank:]]", "") %>%
    strsplit("") %>%
    lapply(table) %>%
    lapply(length) %>%
    unlist
}

word_means <- transcription_matches %>%
  group_by(message_type, seed_id, word, word_category) %>%
  summarize(is_correct = mean(is_correct, na.rm = TRUE)) %>%
  ungroup() %>%
  left_join(performace_labels) %>%
  mutate(
    word_length = nchar(word),
    unique_char = unique_char(word)
  ) %>%
  recode_message_type()

# Drop transcriptions that are too long, and ones that
# only contain a single unique character.

max_word_length <- 10
min_unique_char <- 2
word_means %<>% mutate(
  is_too_long = word_length > max_word_length,
  is_too_short = unique_char < min_unique_char,
  is_word_ok = !is_too_long & !is_too_short)

# Show available transcriptions

ggplot(word_means, aes(x = message_label, y = is_correct)) +
  geom_point(aes(color = is_better_than_chance, shape = is_word_ok),
             position = position_jitterdodge(jitter.width = 0.2, dodge.width = 0.5)) +
  geom_hline(yintercept = 0.25, lty = 2) +
  scale_x_message_label +
  scale_shape_manual("word length ok", labels = c("False", "True"), values = c(1, 16)) +
  scale_color_discrete(paste("p <", alpha), labels = c("False", "True")) +
  labs(title = "Available transcriptions") +
  base_theme +
  theme(legend.position = "bottom")

available_means <- word_means %>% filter(is_better_than_chance == 1, is_word_ok == 1)

# Calculate desired mean and sd based on transcriptions of
# last gen imitations (the lowest performing group).

baseline_group <- filter(available_means, message_type == "last_gen_imitation")
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

max_words_per_message <- 3
max_iterations <- 10000

smart_sample <- function(frame) {
  if (nrow(frame) < max_words_per_message) {
    print(paste('Only', nrow(frame), 'words available for this message.'))
    return(frame)
  }

  for (i in 1:max_iterations) {
    sample <- sample_n(frame, size = max_words_per_message)
    if (check_within_desired_range(sample)) {
      print('Found a sample that works!')
      return(sample)
    }
  }

  print('Unable to find a sample satisfying the desired criteria, returning a random sample')
  sample_n(frame, size = max_words_per_message)
}

sampled_labels <- available_means %>%
  filter(is_correct < 0.8) %>%
  group_by(message_type, seed_id) %>%
  do({ smart_sample(.) }) %>%
  ungroup %>%
  mutate(is_selected = TRUE) %>%
  select(word, is_selected)

available_means %<>% left_join(sampled_labels)

ggplot(available_means, aes(x = message_label, y = is_correct)) +
  geom_point(aes(color = is_selected), position = position_jitterdodge(jitter.width = 0.2, dodge.width = 0.5)) +
  geom_hline(aes(yintercept = is_correct), data = data.frame(is_correct = c(min_mean, max_mean)), lty = 2) +
  coord_cartesian(ylim = c(0, 1)) +
  scale_x_message_label +
  scale_color_discrete("", labels = c("Selected for LSN experiment", "")) +
  base_theme +
  theme(legend.position = "top")

final <- available_means %>%
  filter(is_selected == 1) %>%
  rename(category = word_category) %>%
  select(message_type, seed_id, category, word) %>%
  unique %>%
  arrange(message_type, category, seed_id)

write.csv(final, "stimuli/messages.csv", row.names = FALSE)
