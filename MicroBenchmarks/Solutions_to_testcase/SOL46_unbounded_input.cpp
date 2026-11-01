// Category: Type Errors (Success Case)
// Expected Result: Always use bounds-checked input methods

#include <iostream>
#include <string>

int main() {
    std::string name;  // SUCCESS: Used std::string which handles resizing
    
    std::cout << "Enter your name: ";
    if (std::cin >> name) {
        std::cout << "Hello, " << name << std::endl;
    }
    
    return 0;
}
