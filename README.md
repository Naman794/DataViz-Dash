# DataViz Dash

DataViz Dash is a unique integration between a web application for data visualization and a Discord bot, designed to streamline data interaction and visualization directly within Discord and on a dedicated web platform. This project allows users to upload and visualize Excel data through interactive charts and graphs, with additional functionalities provided through a Discord interface for user verification and data interaction.

## Features

- **Data Visualization**: Upload Excel files via the web application to visualize data through interactive charts and graphs.
- **Discord Integration**: Access data visualization functionalities and user verification directly within Discord.
- **User Verification System**: Secure verification system for new users, integrating seamlessly with Discord and the web application.
- **Sharded Discord Bot**: Utilizes sharding for enhanced performance and scalability across multiple Discord servers.
- **Persistent Configuration**: Configuration and setup statuses are saved across bot restarts and server reboots, ensuring a seamless user experience.

## Getting Started

These instructions will guide you in setting up DataViz Dash and the Discord bot on your local machine for development, testing, and deployment.

### Prerequisites

- Python 3.8+
- discord.py 2.0
- Flask
- MongoDB

### Installation

1. **Clone the Repository**:
   ```sh
   git clone https://github.com/naman794/dataviz-dash.git
   cd dataviz-dash
   ```

2. **Install Dependencies**:
   ```sh
   pip install -r requirements.txt
   ```

3. **Configure Your Application**:
   Create a `config.py` with your Discord bot token and any other necessary configurations.

4. **Run the Application**:
   Start the web application and the Discord bot using:
   ```bash
   python main.py
   ```

## Usage

### Web Application

- Navigate to the web application via your browser to upload Excel files and visualize the data.
- Access the dashboard to interact with uploaded data through dynamic charts and graphs.

### Discord Bot

- Use the `/setup` command in your server to configure the bot.
- Verified users can interact with the bot to upload and visualize data directly within Discord.

## Contributing

This project is currently in development and open for contributions. We aim to make it more robust, adding new features and improving existing functionality. If you're interested in contributing to the project, your input is welcome!

### How to Contribute

1. **Fork the Repository**: Start by forking the repository to your GitHub account.
2. **Create a Branch**: Create a branch in your forked repository for your feature or fix.
3. **Commit Your Changes**: Make your changes in your branch and commit them.
4. **Submit a Pull Request**: Push your changes to your fork and submit a pull request to the main project. Include a clear description of your changes and any other relevant information.

We appreciate contributions of all forms, including bug reports, feature requests, documentation improvements, and code updates. Before submitting your contribution, please review any guidelines specified in the repository or contact the project maintainers.

## License

This project is licensed under the MIT License - see the [LICENSE.md](LICENSE.md) file for details.

## Acknowledgments

- Thanks to the contributors of discord.py for their extensive documentation.
- Appreciation to all testers and users for their valuable feedback.

