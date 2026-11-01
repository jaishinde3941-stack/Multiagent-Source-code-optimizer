// Category: Security Vulnerabilities (Success Case)
// Expected Result: Avoid system() with user input; use safer APIs or sanitize input

#include <iostream>
#include <fstream>
#include <string>

int main() {
    std::string userInput;
    
    std::cout << "Enter filename to display: ";
    if (std::cin >> userInput) {
        // SUCCESS: Avoided system() call; opened file safely using ifstream
        std::ifstream file(userInput);
        if (file.is_open()) {
            std::string line;
            while (std::getline(file, line)) {
                std::cout << line << std::endl;
            }
        } else {
            std::cout << "Could not open file." << std::endl;
        }
    }
    
    return 0;
}
