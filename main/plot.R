# Visualização do dataset mtcars: mpg vs wt, colorido por número de cilindros.

library(tidyverse)

data("mtcars")

mtcars_vis <- mtcars %>%
  as_tibble(rownames = "modelo") %>%
  mutate(cyl = factor(cyl))

cor_val <- cor(mtcars_vis$wt, mtcars_vis$mpg)

plot_mtcars <- ggplot(mtcars_vis, aes(x = wt, y = mpg, color = cyl)) +
  geom_point(size = 3, alpha = 0.9) +
  geom_smooth(method = "lm", se = FALSE, color = "black", linewidth = 1) +
  annotate("segment", x = 4.55, y = 18, xend = 4.5, yend = 13.5,
           arrow = arrow(length = grid::unit(0.15, "inches")), color = "black") +
  annotate("label", x = 4.8, y = 18, label = sprintf("Correlação: %.2f", cor_val),
           fill = "white", color = "black", size = 4) +
  scale_color_brewer(palette = "Dark2", name = "Cilindros") +
  labs(
    title = "Consumo por peso no dataset mtcars",
    x = "Peso (1000 lb)",
    y = "Consumo (milhas por galão)"
  ) +
  theme_minimal(base_size = 13)

ggsave(
  filename = "vis-mtcars.svg",
  plot = plot_mtcars,
  width = 8,
  height = 5
)
