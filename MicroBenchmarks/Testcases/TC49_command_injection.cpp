// Category: Security Vulnerabilities
// Error: Command injection vulnerability

#include <iostream>
#include <cstdlib>
#include <string>

int main() {
    std::string userInput;
    
    std::cout << "Enter filename to display: ";
    std::cin >> userInput;
    
    std::string command = "cat " + userInput;  // ERROR: Command injection
    system(command.c_str());
    
    return 0;
}
